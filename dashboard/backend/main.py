"""
Auto Dashboard API — FastAPI backend serving real-time flight data to the frontend.
"""
import json
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Resolve project root
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from agents.scraper import run_all_missions, fetch_cheapest_dates
from agents.analyzer import get_all_signals, get_price_chart_data, load_history
from agents.tracker import read_status, start_scheduler

app = FastAPI(title="Auto — Autopilot Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = ROOT / "config.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


# ─── Startup: kick off the tracker scheduler ──────────────────────────────────
@app.on_event("startup")
async def startup():
    config = load_config()
    interval = config["autopilot"]["check_interval_minutes"]
    start_scheduler(interval)


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    return read_status()


@app.get("/api/config")
async def get_config():
    return load_config()


@app.get("/api/missions")
async def get_missions():
    config = load_config()
    return config["missions"]


@app.get("/api/prices/live")
async def get_live_prices():
    """Trigger an immediate price fetch for all active missions."""
    try:
        results = await run_all_missions()
        config = load_config()
        missions = {m["id"]: m for m in config["missions"]}
        current_prices = {
            mid: r["offers"][0]["price_total"]
            for mid, r in results.items()
            if r.get("offers")
        }
        signals = get_all_signals(list(missions.values()), current_prices)
        return {
            "offers": results,
            "signals": signals,
            "fetched_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prices/history/{mission_id}")
async def get_price_history(mission_id: str):
    data = get_price_chart_data(mission_id)
    if not data:
        return {"mission_id": mission_id, "points": []}
    return {"mission_id": mission_id, "points": data}


@app.get("/api/signals")
async def get_signals():
    config = load_config()
    history = load_history()
    missions = [m for m in config["missions"] if m.get("active")]
    current_prices = {}
    for m in missions:
        records = history.get(m["id"], [])
        if records:
            current_prices[m["id"]] = records[-1]["price"]
    signals = get_all_signals(missions, current_prices)
    return signals


@app.get("/api/cheapest-dates/{mission_id}")
async def get_cheapest_dates(mission_id: str):
    """
    Checks ±7 days around the target date for cheaper alternatives.
    Uses ~15 SerpAPI calls — run sparingly (not on every poll cycle).
    """
    config = load_config()
    mission = next((m for m in config["missions"] if m["id"] == mission_id), None)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    dates = await fetch_cheapest_dates(mission)
    return {"mission_id": mission_id, "dates": dates}


class MissionUpdate(BaseModel):
    origin: str | None = None
    destination: str | None = None
    depart_date: str | None = None
    passengers: int | None = None
    max_price_per_person: float | None = None
    preferred_airlines: list[str] | None = None
    nonstop_only: bool | None = None
    active: bool | None = None


@app.patch("/api/missions/{mission_id}")
async def update_mission(mission_id: str, update: MissionUpdate):
    config = load_config()
    mission = next((m for m in config["missions"] if m["id"] == mission_id), None)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    for field, val in update.dict(exclude_none=True).items():
        mission[field] = val
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    return mission
