"""
Tracker Agent — polls SerpAPI for nonstop AA round-trip prices (morning + afternoon),
writes public JSON, emails alerts on drops, and pushes to GitHub for Vercel redeploy.
"""
import asyncio
import json
import subprocess
from pathlib import Path
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from agents.scraper import run_all_trips
from agents.analyzer import record_prices, get_all_signals, get_price_chart_data
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


def write_public_data(config: dict, signals: list, options_map: dict):
    history = {t["id"]: get_price_chart_data(t["id"])[-60:] for t in config["trips"] if t.get("active")}
    payload = {
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "trips": [t for t in config["trips"] if t.get("active")],
        "flight_options": options_map,
        "signals": signals,
        "history": history,
    }
    PUBLIC_JSON.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_JSON.write_text(json.dumps(payload, indent=2))
    print(f"[Tracker] Public JSON updated.")


def git_push():
    try:
        subprocess.run(
            ["git", "add",
             "dashboard/frontend/public/data/autopilot.json",
             "dashboard/frontend/public/data/price_history.json"],
            cwd=REPO_ROOT, check=True, capture_output=True,
        )
        if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT, capture_output=True).returncode == 0:
            print("[Tracker] No price changes — skipping push.")
            return
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        subprocess.run(["git", "commit", "-m", f"Auto: price update {ts}"],
                       cwd=REPO_ROOT, check=True, capture_output=True)
        subprocess.run(["git", "push", "origin", "main"],
                       cwd=REPO_ROOT, check=True, capture_output=True)
        print("[Tracker] Pushed to GitHub → Vercel redeploy triggered.")
    except subprocess.CalledProcessError as e:
        print(f"[Tracker] Git push failed: {e.stderr.decode().strip()}")


async def poll_cycle():
    config = load_config()
    trips = {t["id"]: t for t in config["trips"] if t.get("active")}
    print(f"[Tracker] Poll cycle @ {datetime.utcnow().isoformat()}")

    try:
        results = await run_all_trips()
    except Exception as e:
        print(f"[Tracker] Scraper error: {e}")
        status = read_status()
        status.setdefault("errors", []).append({"ts": datetime.utcnow().isoformat(), "error": str(e)})
        status["errors"] = status["errors"][-20:]
        write_status(status)
        return

    options_map = {}
    for trip_id, result in results.items():
        if result.get("error"):
            print(f"[Tracker] Error for {trip_id}: {result['error']}")
            continue
        opts = result.get("options", {})
        if not opts:
            continue

        options_map[trip_id] = opts
        morning_ppp = opts.get("morning", {}).get("price_per_person")
        afternoon_ppp = opts.get("afternoon", {}).get("price_per_person")
        record_prices(trip_id, morning_ppp, afternoon_ppp)

        m_str = f"${morning_ppp:.0f}/person" if morning_ppp else "N/A"
        a_str = f"${afternoon_ppp:.0f}/person" if afternoon_ppp else "N/A"
        print(f"[Tracker] {trip_id} → morning: {m_str}, afternoon: {a_str}")

    signals = get_all_signals(list(trips.values()), options_map)
    for sig in signals:
        trip = trips[sig["trip_id"]]
        check_and_alert(trip, sig, options_map.get(sig["trip_id"], {}))

    write_public_data(config, signals, options_map)
    git_push()

    status = read_status()
    status["last_run"] = datetime.utcnow().isoformat()
    status["runs"] = status.get("runs", 0) + 1
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
