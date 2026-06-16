"""
Scraper Agent — round-trip price search via SerpAPI Google Flights.
Filters: American Airlines only, nonstop only.
Returns morning (5am-11:59am) and afternoon (12pm-5:59pm) departure slots,
plus Google's own price_insights (level, typical range, 30-day history).
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
    """Parse '7:45 AM' → 7, '2:15 PM' → 14."""
    try:
        return datetime.strptime(time_str.strip(), "%I:%M %p").hour
    except Exception:
        return None


def _time_slot(time_str: str) -> str:
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




def _parse_price_insights(raw_insights: dict, passengers: int) -> dict:
    """
    Extract and normalize Google's price intelligence.
    Google stores price_history as [[epoch_ms, price_total], ...].
    We convert to per-person and ISO timestamps.
    """
    if not raw_insights:
        return {}

    level = raw_insights.get("price_level")  # "low" | "typical" | "high"
    typical = raw_insights.get("typical_range")  # [low_total, high_total]
    lowest = raw_insights.get("lowest_price")    # total price

    # Google's 30-day price history — [[epoch_ms, total_price], ...]
    raw_history = raw_insights.get("price_history", [])
    history_ppp = []
    for entry in raw_history:
        if isinstance(entry, list) and len(entry) == 2:
            ts_ms, price_total = entry
            try:
                ts = datetime.utcfromtimestamp(ts_ms / 1000).isoformat()
                history_ppp.append({
                    "ts": ts,
                    "price_per_person": round(float(price_total) / passengers, 2),
                    "price_total": float(price_total),
                })
            except Exception:
                continue

    return {
        "price_level": level,
        "typical_range_ppp": [round(typical[0] / passengers, 2), round(typical[1] / passengers, 2)] if typical and len(typical) == 2 else None,
        "lowest_ppp": round(lowest / passengers, 2) if lowest else None,
        "google_history_ppp": history_ppp,  # ~30 data points, per-person
    }


async def fetch_trip_options(trip: dict) -> dict:
    """
    Fetch nonstop AA round-trip options.
    Returns { morning, afternoon, price_insights, aa_nonstop_count }
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

    # Google's price intelligence (free with every response)
    price_insights = _parse_price_insights(raw.get("price_insights", {}), trip["passengers"])

    # Collect all AA nonstop flights, grouped by time slot
    slots: dict[str, list] = {"morning": [], "afternoon": []}
    aa_nonstop_count = 0

    all_flights = raw.get("best_flights", []) + raw.get("other_flights", [])
    for flight in all_flights:
        price_total = float(flight.get("price", 0))
        if price_total == 0:
            continue
        legs = flight.get("flights", [])
        if not legs:
            continue

        outbound = legs[0]
        airline = outbound.get("airline", "")
        if not _is_american(airline):
            continue

        aa_nonstop_count += 1
        depart_time = outbound.get("departure_airport", {}).get("time", "")
        arrive_time = outbound.get("arrival_airport", {}).get("time", "")
        slot = _time_slot(depart_time)
        if slot not in ("morning", "afternoon"):
            continue

        # Return leg is legs[1] for nonstop round trips (when SerpAPI includes it)
        return_leg = legs[1] if len(legs) > 1 else None

        slots[slot].append({
            "available": True,
            "price_total": price_total,
            "price_per_person": round(price_total / trip["passengers"], 2),
            "depart_time": depart_time,
            "arrive_time": arrive_time,
            "flight_number": outbound.get("flight_number", ""),
            "airline": airline,
            # Return leg details if SerpAPI includes them
            "return_flight_number": return_leg.get("flight_number") if return_leg else None,
            "return_depart_time": return_leg.get("departure_airport", {}).get("time") if return_leg else None,
            "return_arrive_time": return_leg.get("arrival_airport", {}).get("time") if return_leg else None,
        })

    # Sort each slot cheapest first
    for s in slots:
        slots[s].sort(key=lambda x: x["price_total"])

    return {
        "morning": slots["morning"],    # [] = no flights that slot
        "afternoon": slots["afternoon"],
        "price_insights": price_insights,
        "aa_nonstop_count": aa_nonstop_count,
    }


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
