"""
Scraper Agent — round-trip price search via SerpAPI Google Flights.
Filters: American Airlines only, nonstop only.
Returns morning (5am-11:59am) and afternoon (12pm-5:59pm) departure slots separately.
"""
import os
import json
import httpx
from datetime import datetime, date, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

CONFIG_PATH = Path(__file__).parent.parent / "config.json"
SERPAPI_BASE = "https://serpapi.com/search"
_CABIN = {"ECONOMY": 1, "PREMIUM_ECONOMY": 2, "BUSINESS": 3, "FIRST": 4}


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def _parse_hour(time_str: str) -> int | None:
    """Parse '7:45 AM' → 7, '2:15 PM' → 14. Returns None on failure."""
    try:
        return datetime.strptime(time_str.strip(), "%I:%M %p").hour
    except Exception:
        return None


def _time_slot(time_str: str) -> str:
    """Categorize departure time as morning, afternoon, or other."""
    hour = _parse_hour(time_str)
    if hour is None:
        return "other"
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    return "other"


def _is_american(airline_name: str) -> bool:
    return "american" in airline_name.lower()


EMPTY_SLOT = {
    "available": False,
    "price_total": None,
    "price_per_person": None,
    "depart_time": None,
    "flight_number": None,
    "airline": None,
}


async def fetch_trip_options(trip: dict) -> dict:
    """
    Fetch nonstop American Airlines round-trip options for a trip.
    Returns { morning: {...}, afternoon: {...} } with per-person pricing.
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise ValueError("SERPAPI_KEY not set in .env")

    params = {
        "engine": "google_flights",
        "api_key": api_key,
        "departure_id": trip["origin"],
        "arrival_id": trip["destination"],
        "outbound_date": trip["depart_date"],
        "return_date": trip["return_date"],
        "adults": trip["passengers"],
        "travel_class": _CABIN.get(trip["cabin_class"], 1),
        "currency": "USD",
        "hl": "en",
        "type": "1",   # round trip
        "stops": "1",  # nonstop only
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(SERPAPI_BASE, params=params)
        resp.raise_for_status()
        raw = resp.json()

    slots: dict[str, dict] = {"morning": {}, "afternoon": {}}

    all_flights = raw.get("best_flights", []) + raw.get("other_flights", [])
    for flight in all_flights:
        price_total = float(flight.get("price", 0))
        if price_total == 0:
            continue

        legs = flight.get("flights", [])
        if not legs:
            continue

        # Outbound leg is always first
        outbound = legs[0]
        airline = outbound.get("airline", "")

        # American only
        if not _is_american(airline):
            continue

        depart_time = outbound.get("departure_airport", {}).get("time", "")
        slot = _time_slot(depart_time)
        if slot not in ("morning", "afternoon"):
            continue

        # Keep cheapest per slot
        if not slots[slot] or price_total < slots[slot].get("price_total", float("inf")):
            flight_number = outbound.get("flight_number", "")
            slots[slot] = {
                "available": True,
                "price_total": price_total,
                "price_per_person": round(price_total / trip["passengers"], 2),
                "depart_time": depart_time,
                "flight_number": flight_number,
                "airline": airline,
            }

    return {
        "morning": slots["morning"] if slots["morning"] else EMPTY_SLOT.copy(),
        "afternoon": slots["afternoon"] if slots["afternoon"] else EMPTY_SLOT.copy(),
    }


async def fetch_cheapest_dates(trip: dict) -> list[dict]:
    """Check ±5 days (nonstop AA) — costs 10 API calls, run manually."""
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        return []

    depart = date.fromisoformat(trip["depart_date"])
    duration = trip["duration_days"]
    results = []

    async with httpx.AsyncClient(timeout=20) as client:
        for offset in range(-5, 6):
            out = depart + timedelta(days=offset)
            ret = out + timedelta(days=duration)
            try:
                resp = await client.get(
                    SERPAPI_BASE,
                    params={
                        "engine": "google_flights",
                        "api_key": api_key,
                        "departure_id": trip["origin"],
                        "arrival_id": trip["destination"],
                        "outbound_date": out.isoformat(),
                        "return_date": ret.isoformat(),
                        "adults": trip["passengers"],
                        "travel_class": _CABIN.get(trip["cabin_class"], 1),
                        "currency": "USD",
                        "hl": "en",
                        "type": "1",
                        "stops": "1",
                    },
                    timeout=15,
                )
                data = resp.json()
                # Filter to American only
                aa_flights = [
                    f for f in (data.get("best_flights", []) + data.get("other_flights", []))
                    if f.get("flights") and _is_american(f["flights"][0].get("airline", ""))
                ]
                if aa_flights:
                    best = float(aa_flights[0].get("price", 0))
                    if best > 0:
                        results.append({
                            "depart_date": out.isoformat(),
                            "return_date": ret.isoformat(),
                            "price": best,
                            "price_per_person": round(best / trip["passengers"], 2),
                        })
            except Exception:
                continue

    return sorted(results, key=lambda x: x["price"])


async def run_all_trips() -> dict:
    config = load_config()
    results = {}
    for trip in config["trips"]:
        if not trip.get("active"):
            continue
        try:
            options = await fetch_trip_options(trip)
            results[trip["id"]] = {"options": options, "error": None}
        except Exception as e:
            results[trip["id"]] = {"error": str(e), "options": None}
    return results
