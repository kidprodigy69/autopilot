"""
Scraper Agent — round-trip price search via SerpAPI Google Flights.
Filters: American Airlines (including AA-numbered regional codeshares), nonstop outbound only.
Returns morning (5am–11:59am) and afternoon (12pm–5:59pm) departure slots.
"""
import os
import re
import json
import httpx
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

CONFIG_PATH = Path(__file__).parent.parent / "config.json"
SERPAPI_BASE = "https://serpapi.com/search"
_CABIN = {"ECONOMY": 1, "PREMIUM_ECONOMY": 2, "BUSINESS": 3, "FIRST": 4}

# AA regional partners — they operate under AA flight numbers (AA XXXX)
# but SerpAPI may return the operating carrier name instead of "American"
_AA_REGIONAL = {
    "envoy", "psa", "piedmont", "skywest", "mesa", "republic",
    "american eagle", "compass", "trans states", "chautauqua",
}


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def _parse_hour(time_str: str) -> int | None:
    """
    Parse departure time to hour. Handles any format SerpAPI might return:
      '7:45 AM'              → 7
      '12:30 PM'             → 12
      '07:45'                → 7   (24h)
      '19:45'                → 19  (24h)
      '2026-08-19 7:45 AM'   → 7   (date-prefixed)
      '2026-08-19T07:45:00'  → 7   (ISO)
    Uses regex to extract the time regardless of surrounding context.
    """
    s = ' '.join(time_str.split())  # normalize all whitespace

    # Try exact strptime matches first (fastest path)
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).hour
        except ValueError:
            pass

    # Regex: find HH:MM optionally followed by AM/PM anywhere in the string
    m = re.search(r'(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM|am|pm)?', s)
    if m:
        hour = int(m.group(1))
        ampm = (m.group(3) or "").upper()
        if ampm == "PM" and hour != 12:
            hour += 12
        elif ampm == "AM" and hour == 12:
            hour = 0
        return hour

    return None


def _time_slot(time_str: str) -> str:
    hour = _parse_hour(time_str)
    if hour is None:
        print(f"    [time-parse FAIL] could not parse: {repr(time_str)}")
        return "other"
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 19:  # up to 6:59pm
        return "afternoon"
    return "other"


def _is_american(airline_name: str, flight_number: str = "") -> bool:
    """
    True if this is an American-marketed flight.
    Catches:
      - "American Airlines" (mainline)
      - Flight numbers starting with "AA" (regional codeshares: Envoy, PSA, Piedmont, etc.)
      - Known AA regional partner names as fallback
    """
    name_lower = airline_name.lower()
    fn_upper = flight_number.upper().replace(" ", "")

    if "american" in name_lower:
        return True
    if fn_upper.startswith("AA") and fn_upper[2:].isdigit():
        return True
    for regional in _AA_REGIONAL:
        if regional in name_lower:
            return True
    return False


def _parse_price_insights(raw_insights: dict, passengers: int) -> dict:
    if not raw_insights:
        return {}

    level = raw_insights.get("price_level")
    typical = raw_insights.get("typical_range")
    lowest = raw_insights.get("lowest_price")
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
        "typical_range_ppp": (
            [round(typical[0] / passengers, 2), round(typical[1] / passengers, 2)]
            if typical and len(typical) == 2 else None
        ),
        "lowest_ppp": round(lowest / passengers, 2) if lowest else None,
        "google_history_ppp": history_ppp,
    }


async def fetch_trip_options(trip: dict, debug: bool = False) -> dict:
    """
    Fetch nonstop AA round-trip options for a trip.
    Returns { morning: [...], afternoon: [...], price_insights: {...}, aa_nonstop_count: int }
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
        # NOT passing stops=1 — we post-filter for nonstop ourselves
        # so we don't miss round trips where return leg isn't nonstop
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(SERPAPI_BASE, params=params)
        resp.raise_for_status()
        raw = resp.json()

    if debug:
        print("\n=== RAW SERPAPI RESPONSE ===")
        print(json.dumps(raw, indent=2)[:8000])  # first 8k chars
        print("=== END RAW ===\n")

    price_insights = _parse_price_insights(raw.get("price_insights", {}), trip["passengers"])

    slots: dict[str, list] = {"morning": [], "afternoon": []}
    aa_nonstop_count = 0
    total_seen = 0

    all_flights = raw.get("best_flights", []) + raw.get("other_flights", [])
    print(f"[Scraper] {trip['id']}: {len(all_flights)} total results from SerpAPI")

    for flight in all_flights:
        total_seen += 1
        price_total = float(flight.get("price", 0))
        if price_total == 0:
            continue

        legs = flight.get("flights", [])
        if not legs:
            continue

        outbound = legs[0]
        airline = outbound.get("airline", "")
        flight_number = outbound.get("flight_number", "")

        # Post-filter: nonstop outbound = no layovers on outbound leg
        # SerpAPI puts layovers in the top-level "layovers" field
        has_layover = bool(flight.get("layovers"))
        if has_layover:
            if debug:
                print(f"  SKIP (layover): {flight_number} {airline} ${price_total}")
            continue

        # American Airlines or AA-numbered codeshare
        if not _is_american(airline, flight_number):
            if debug:
                print(f"  SKIP (not AA): {flight_number} {airline} ${price_total}")
            continue

        aa_nonstop_count += 1
        depart_time = outbound.get("departure_airport", {}).get("time", "")
        arrive_time = outbound.get("arrival_airport", {}).get("time", "")
        slot = _time_slot(depart_time)

        print(f"  ✓ {flight_number} ({airline}) {depart_time}→{arrive_time} ${price_total:.0f} [{slot}]")

        if slot not in ("morning", "afternoon"):
            if debug:
                print(f"    → outside morning/afternoon window, skipping")
            continue

        # Return leg — may be present for nonstop round trips
        return_leg = legs[1] if len(legs) > 1 else None

        slots[slot].append({
            "available": True,
            "price_total": price_total,
            "price_per_person": round(price_total / trip["passengers"], 2),
            "depart_time": depart_time,
            "arrive_time": arrive_time,
            "flight_number": flight_number,
            "airline": airline,
            "return_flight_number": return_leg.get("flight_number") if return_leg else None,
            "return_depart_time": return_leg.get("departure_airport", {}).get("time") if return_leg else None,
            "return_arrive_time": return_leg.get("arrival_airport", {}).get("time") if return_leg else None,
            "booking_token": flight.get("booking_token"),
        })

    for s in slots:
        slots[s].sort(key=lambda x: x["price_total"])

    print(f"[Scraper] {trip['id']}: {aa_nonstop_count} AA nonstop → morning:{len(slots['morning'])} afternoon:{len(slots['afternoon'])}")

    # Kayak pre-filled search URL — the most reliable deep-link for flight search.
    # Tested approaches that failed:
    #   - aa.com/booking/search#/roundTrip/... → 404 (SPA not served from that path)
    #   - aa.com/booking/choose-flights/1.do → session-timeout (requires active session)
    #   - google.com/travel/flights?hl=en#flt=... → page loads but ignores hash params
    # Kayak's URL format is stable, documented, and pre-fills origin/dest/dates/pax.
    # Filters: nonstop only (stops=0) + American Airlines only (airlines=AA).
    # User flow: Kayak shows matching AA flights → click one → "Book on American.com" → AA checkout.
    aa_booking_url = (
        f"https://www.kayak.com/flights"
        f"/{trip['origin']}-{trip['destination']}"
        f"/{trip['depart_date']}/{trip['return_date']}"
        f"/{trip['passengers']}adults"
        f"?fs=stops%3D0%2Cairlines%3DAA"
    )

    return {
        "morning": slots["morning"],
        "afternoon": slots["afternoon"],
        "price_insights": price_insights,
        "aa_nonstop_count": aa_nonstop_count,
        "aa_booking_url": aa_booking_url,
    }


async def run_all_trips(debug: bool = False) -> dict:
    config = load_config()
    results = {}
    for trip in config["trips"]:
        if not trip.get("active"):
            continue
        try:
            options = await fetch_trip_options(trip, debug=debug)
            results[trip["id"]] = {"options": options, "error": None}
        except Exception as e:
            results[trip["id"]] = {"error": str(e), "options": None}
            print(f"[Scraper] ERROR for {trip['id']}: {e}")
    return results
