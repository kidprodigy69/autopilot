"""
Tracker Agent — polls SerpAPI for nonstop AA round-trip prices (morning + afternoon),
writes public JSON, emails alerts on drops, and pushes to GitHub for Vercel redeploy.
Includes a monthly API budget guard: stops polling if within 5 calls of the monthly cap.
"""
import asyncio
import json
import subprocess
from pathlib import Path
from datetime import datetime

from agents.scraper import run_all_trips
from agents.analyzer import record_prices, seed_from_google, get_all_signals, get_price_chart_data
from agents.reporter import check_and_alert, send_status_update

CONFIG_PATH = Path(__file__).parent.parent / "config.json"
STATUS_PATH = Path(__file__).parent.parent / "data" / "tracker_status.json"
BUDGET_PATH = Path(__file__).parent.parent / "data" / "api_budget.json"
PUBLIC_JSON = Path(__file__).parent.parent / "dashboard" / "frontend" / "public" / "data" / "autopilot.json"
REPO_ROOT = Path(__file__).parent.parent


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


# ── Monthly API budget tracking ──────────────────────────────────────────────

def _budget_key() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def load_budget() -> dict:
    if not BUDGET_PATH.exists():
        return {}
    return json.loads(BUDGET_PATH.read_text())


def save_budget(data: dict):
    BUDGET_PATH.parent.mkdir(parents=True, exist_ok=True)
    BUDGET_PATH.write_text(json.dumps(data, indent=2))


def check_budget(trips_count: int) -> bool:
    """
    Returns True if OK to proceed. False if this cycle would push us past the monthly cap.
    trips_count = number of API calls this cycle will make (one per active trip).
    """
    config = load_config()
    cap = config.get("serpapi", {}).get("monthly_budget", 245)
    budget = load_budget()
    key = _budget_key()
    used = budget.get(key, 0)
    if used + trips_count > cap:
        print(f"[Tracker] BUDGET CAP: {used} used + {trips_count} needed > {cap} monthly limit. Skipping poll.")
        return False
    return True


def record_api_calls(count: int):
    budget = load_budget()
    key = _budget_key()
    budget[key] = budget.get(key, 0) + count
    save_budget(budget)
    cap = load_config().get("serpapi", {}).get("monthly_budget", 245)
    print(f"[Tracker] API budget: {budget[key]}/{cap} used this month ({_budget_key()})")


# ── Data writing ─────────────────────────────────────────────────────────────

def write_status(status: dict):
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, indent=2))


def read_status() -> dict:
    if not STATUS_PATH.exists():
        return {"last_run": None, "runs": 0, "errors": []}
    return json.loads(STATUS_PATH.read_text())


def write_public_data(config: dict, signals: list, options_map: dict):
    history = {t["id"]: get_price_chart_data(t["id"])[-120:] for t in config["trips"] if t.get("active")}
    payload = {
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "trips": [t for t in config["trips"] if t.get("active")],
        "flight_options": options_map,
        "signals": signals,
        "history": history,
    }
    PUBLIC_JSON.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_JSON.write_text(json.dumps(payload, indent=2))
    print("[Tracker] Public JSON written.")


# ── Main poll cycle ──────────────────────────────────────────────────────────

async def poll_cycle():
    config = load_config()
    active_trips = [t for t in config["trips"] if t.get("active")]
    trips = {t["id"]: t for t in active_trips}

    print(f"\n[Tracker] Poll cycle @ {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    # Check budget before making any API calls
    if not check_budget(len(active_trips)):
        return

    try:
        results = await run_all_trips()
    except Exception as e:
        print(f"[Tracker] Scraper error: {e}")
        status = read_status()
        status.setdefault("errors", []).append({"ts": datetime.utcnow().isoformat(), "error": str(e)})
        status["errors"] = status["errors"][-20:]
        write_status(status)
        raise  # re-raise so GitHub Actions marks the run as failed

    # Record API calls actually made
    calls_made = sum(1 for r in results.values() if not r.get("error"))
    failed = sum(1 for r in results.values() if r.get("error"))
    record_api_calls(calls_made)

    options_map = {}
    for trip_id, result in results.items():
        if result.get("error"):
            print(f"[Tracker] Error for {trip_id}: {result['error']}")
            continue
        opts = result.get("options", {})
        if not opts:
            continue

        options_map[trip_id] = opts
        morning_list = opts.get("morning", [])
        afternoon_list = opts.get("afternoon", [])
        morning_ppp = morning_list[0].get("price_per_person") if morning_list else None
        afternoon_ppp = afternoon_list[0].get("price_per_person") if afternoon_list else None
        price_insights = opts.get("price_insights", {})
        aa_count = opts.get("aa_nonstop_count", 0)

        # Seed history from Google's 30-day data on first run
        google_history = price_insights.get("google_history_ppp", [])
        if google_history:
            seed_from_google(trip_id, google_history)

        record_prices(trip_id, morning_ppp, afternoon_ppp)

        m_str = f"${morning_ppp:.0f}/pp" if morning_ppp else "none"
        a_str = f"${afternoon_ppp:.0f}/pp" if afternoon_ppp else "none"
        level = price_insights.get("price_level") or "?"
        print(f"[Tracker] {trip_id}: morning={m_str} afternoon={a_str} google={level} aa_flights={aa_count}")

    signals = get_all_signals(list(trips.values()), options_map)

    # Check each trip for price drops; collect results for the status email
    signals_map = {s["trip_id"]: s for s in signals}
    drop_trips: dict[str, float] = {}
    for sig in signals:
        trip = trips[sig["trip_id"]]
        dropped, drop_pct = check_and_alert(trip, sig, options_map.get(sig["trip_id"], {}))
        if dropped:
            drop_trips[trip["id"]] = drop_pct

    # Always send a status email at every poll cycle
    send_status_update(active_trips, signals_map, options_map, drop_trips or None)

    write_public_data(config, signals, options_map)

    status = read_status()
    status["last_run"] = datetime.utcnow().isoformat()
    status["runs"] = status.get("runs", 0) + 1
    if failed:
        status.setdefault("errors", []).append({
            "ts": datetime.utcnow().isoformat(),
            "error": f"{failed} trip(s) failed to fetch",
        })
        status["errors"] = status["errors"][-20:]
    write_status(status)
    print(f"[Tracker] Done. {calls_made} API calls made, {failed} errors.\n")
