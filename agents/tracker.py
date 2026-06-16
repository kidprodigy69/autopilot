"""
Tracker Agent — polls SerpAPI on schedule, records prices, triggers analyzer +
reporter, writes compiled data to public JSON, and pushes to GitHub so Vercel
auto-redeploys the live site.
"""
import asyncio
import json
import subprocess
from pathlib import Path
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from agents.scraper import run_all_missions
from agents.analyzer import record_price, get_all_signals, get_price_chart_data
from agents.reporter import check_and_alert

CONFIG_PATH = Path(__file__).parent.parent / "config.json"
STATUS_PATH = Path(__file__).parent.parent / "data" / "tracker_status.json"
PUBLIC_JSON = Path(__file__).parent.parent / "dashboard" / "frontend" / "public" / "data" / "autopilot.json"
REPO_ROOT = Path(__file__).parent.parent


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def write_status(status: dict):
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, indent=2))


def read_status() -> dict:
    if not STATUS_PATH.exists():
        return {"last_run": None, "runs": 0, "errors": []}
    return json.loads(STATUS_PATH.read_text())


def write_public_data(config: dict, signals: list, current_prices: dict):
    """Compile all data into one JSON file served by the Vercel site."""
    history = {}
    best_offers = {}
    for m in config["missions"]:
        if not m.get("active"):
            continue
        # Last 60 data points for the chart
        history[m["id"]] = get_price_chart_data(m["id"])[-60:]
        price = current_prices.get(m["id"])
        if price:
            best_offers[m["id"]] = {"price_total": price}

    payload = {
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "missions": [m for m in config["missions"] if m.get("active")],
        "signals": signals,
        "history": history,
        "best_offers": best_offers,
    }
    PUBLIC_JSON.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_JSON.write_text(json.dumps(payload, indent=2))
    print(f"[Tracker] Public JSON updated → {PUBLIC_JSON}")


def git_push():
    """Commit the updated autopilot.json and push so Vercel redeploys."""
    try:
        subprocess.run(
            ["git", "add", "dashboard/frontend/public/data/autopilot.json"],
            cwd=REPO_ROOT, check=True, capture_output=True,
        )
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=REPO_ROOT, capture_output=True,
        )
        if result.returncode == 0:
            print("[Tracker] No data changes — skipping push.")
            return
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        subprocess.run(
            ["git", "commit", "-m", f"Auto: price update {ts}"],
            cwd=REPO_ROOT, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=REPO_ROOT, check=True, capture_output=True,
        )
        print(f"[Tracker] Pushed to GitHub → Vercel redeploy triggered.")
    except subprocess.CalledProcessError as e:
        print(f"[Tracker] Git push failed: {e.stderr.decode().strip()}")


async def poll_cycle():
    config = load_config()
    missions = {m["id"]: m for m in config["missions"] if m.get("active")}
    print(f"[Tracker] Poll cycle @ {datetime.utcnow().isoformat()}")

    try:
        results = await run_all_missions()
    except Exception as e:
        print(f"[Tracker] Scraper error: {e}")
        status = read_status()
        status["errors"].append({"ts": datetime.utcnow().isoformat(), "error": str(e)})
        status["errors"] = status["errors"][-20:]
        write_status(status)
        return

    current_prices = {}
    for mission_id, result in results.items():
        if result.get("error") or not result["offers"]:
            print(f"[Tracker] No offers for {mission_id}: {result.get('error')}")
            continue
        best = result["offers"][0]
        price = best["price_total"]
        airline = best.get("airline", "")
        current_prices[mission_id] = price
        record_price(mission_id, price, airline)
        print(f"[Tracker] {mission_id}: ${price:.2f} via {airline}")

    signals = get_all_signals(list(missions.values()), current_prices)

    for sig in signals:
        mission = missions[sig["mission_id"]]
        check_and_alert(mission, sig["current_price"], sig)

    write_public_data(config, signals, current_prices)
    git_push()

    status = read_status()
    status["last_run"] = datetime.utcnow().isoformat()
    status["runs"] = status.get("runs", 0) + 1
    status["last_prices"] = current_prices
    write_status(status)


def start_scheduler(interval_minutes: int = 720) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        poll_cycle,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="poll_cycle",
        next_run_time=datetime.now(),
    )
    scheduler.start()
    print(f"[Tracker] Scheduler started — polling every {interval_minutes}min")
    return scheduler
