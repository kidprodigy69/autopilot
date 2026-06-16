"""
Scraper Agent — fetches live pricing via SerpAPI's Google Flights endpoint.
Free plan: 250 searches/month. At 2 flights × 4 checks/day = 240/month — fits clean.
"""
import os
import json
import httpx
import asyncio
from datetime import datetime, date, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

CONFIG_PATH = Path(__file__).parent.parent / "config.json"
SERPAPI_BASE = "https://serpapi.com/search"

_CABIN = {"ECONOMY": 1, "PREMIUM_ECONOMY": 2, "BUSINESS": 3, "FIRST": 4}


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


async def fetch_flight_offers(mission: dict) -> list[dict]:
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise ValueError("SERPAPI_KEY not set in .env")

    params = {
        "engine": "google_flights",
        "api_key": api_key,
        "departure_id": mission["origin"],
        "arrival_id": mission["destination"],
        "outbound_date": mission["depart_date"],
        "adults": mission["passengers"],
        "travel_class": _CABIN.get(mission["cabin_class"], 1),
        "currency": "USD",
        "hl": "en",
        "type": "2",  # one-way
    }
    if mission.get("nonstop_only"):
        params["stops"] = "1"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(SERPAPI_BASE, params=params)
        resp.raise_for_status()
        raw = resp.json()

    offers = []
    for flight in raw.get("best_flights", []) + raw.get("other_flights", []):
        price_total = float(flight.get("price", 0))
        if price_total == 0:
            continue

        legs = flight.get("flights", [{}])
        first, last = legs[0], legs[-1]
        airline_code = first.get("airline", "")

        offers.append({
            "price_total": price_total,
            "price_per_person": round(price_total / mission["passengers"], 2),
            "stops": len(legs) - 1,
            "airline": first.get("airline", ""),
            "airline_logo": first.get("airline_logo", ""),
            "duration_minutes": flight.get("total_duration", 0),
            "depart_time": first.get("departure_airport", {}).get("time", ""),
            "arrive_time": last.get("arrival_airport", {}).get("time", ""),
            "fetched_at": datetime.utcnow().isoformat(),
            "mission_id": mission["id"],
        })

    return sorted(offers, key=lambda x: x["price_total"])


async def fetch_cheapest_dates(mission: dict) -> list[dict]:
    """
    Checks ±5 days around the target date for cheaper alternatives.
    Costs 10 API calls — call this manually from the dashboard, not on every poll.
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        return []

    target = date.fromisoformat(mission["depart_date"])
    date_range = [target + timedelta(days=i) for i in range(-5, 6)]

    results = []
    async with httpx.AsyncClient(timeout=20) as client:
        for d in date_range:
            try:
                resp = await client.get(
                    SERPAPI_BASE,
                    params={
                        "engine": "google_flights",
                        "api_key": api_key,
                        "departure_id": mission["origin"],
                        "arrival_id": mission["destination"],
                        "outbound_date": d.isoformat(),
                        "adults": mission["passengers"],
                        "travel_class": 1,
                        "currency": "USD",
                        "hl": "en",
                        "type": "2",
                    },
                    timeout=15,
                )
                data = resp.json()
                flights = data.get("best_flights", []) + data.get("other_flights", [])
                if flights:
                    best = float(flights[0].get("price", 0))
                    if best > 0:
                        results.append({"date": d.isoformat(), "price": best})
            except Exception:
                continue

    return sorted(results, key=lambda x: x["price"])


async def run_all_missions() -> dict:
    config = load_config()
    results = {}
    for m in config["missions"]:
        if not m.get("active"):
            continue
        try:
            offers = await fetch_flight_offers(m)
            results[m["id"]] = {"offers": offers, "error": None}
        except Exception as e:
            results[m["id"]] = {"error": str(e), "offers": []}
    return results
