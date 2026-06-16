"""
Scraper Agent — round-trip price search via SerpAPI Google Flights.
Fetches combined outbound + return price as one total per trip.
Free plan: 250 searches/month. 2 trips x 2 checks/day x 30 days = 120/month.
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


async def fetch_trip_offers(trip: dict) -> list[dict]:
    """Fetch round-trip flight offers for a trip (outbound + return combined)."""
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
        "type": "1",  # 1 = round trip
    }
    if trip.get("nonstop_only"):
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

        # Round trip results have two itineraries: [0] outbound, [1] return
        legs = flight.get("flights", [{}])
        first_leg = legs[0] if legs else {}
        airline = first_leg.get("airline", "")

        offers.append({
            "price_total": price_total,
            "price_per_person": round(price_total / trip["passengers"], 2),
            "stops_outbound": flight.get("layovers", 0),
            "airline": airline,
            "airline_logo": first_leg.get("airline_logo", ""),
            "total_duration_minutes": flight.get("total_duration", 0),
            "depart_time": first_leg.get("departure_airport", {}).get("time", ""),
            "fetched_at": datetime.utcnow().isoformat(),
            "trip_id": trip["id"],
        })

    return sorted(offers, key=lambda x: x["price_total"])


async def fetch_cheapest_dates(trip: dict) -> list[dict]:
    """
    Varies the outbound date ±5 days (keeping trip duration fixed) to find
    cheaper windows. Costs 10 API calls — call from dashboard manually.
    """
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
                    },
                    timeout=15,
                )
                data = resp.json()
                flights = data.get("best_flights", []) + data.get("other_flights", [])
                if flights:
                    best = float(flights[0].get("price", 0))
                    if best > 0:
                        results.append({
                            "depart_date": out.isoformat(),
                            "return_date": ret.isoformat(),
                            "price": best,
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
            offers = await fetch_trip_offers(trip)
            results[trip["id"]] = {"offers": offers, "error": None}
        except Exception as e:
            results[trip["id"]] = {"error": str(e), "offers": []}
    return results
