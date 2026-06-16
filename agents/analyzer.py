"""
Analyzer Agent — tracks morning and afternoon round-trip prices per trip,
detects trends, and emits BUY / HOLD / WAIT signals.
"""
import json
import numpy as np
from pathlib import Path
from datetime import datetime, date
from dataclasses import dataclass, asdict

HISTORY_PATH = Path(__file__).parent.parent / "dashboard" / "frontend" / "public" / "data" / "price_history.json"


def load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {}
    return json.loads(HISTORY_PATH.read_text())


def save_history(history: dict):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2))


def record_prices(trip_id: str, morning_price: float | None, afternoon_price: float | None):
    history = load_history()
    if trip_id not in history:
        history[trip_id] = []
    entry = {"ts": datetime.utcnow().isoformat()}
    if morning_price is not None:
        entry["morning"] = morning_price
    if afternoon_price is not None:
        entry["afternoon"] = afternoon_price
    if len(entry) > 1:  # has at least one price
        history[trip_id].append(entry)
        history[trip_id] = history[trip_id][-500:]
        save_history(history)


def get_price_chart_data(trip_id: str) -> list[dict]:
    history = load_history()
    records = history.get(trip_id, [])
    return [
        {
            "ts": r["ts"],
            "morning": r.get("morning"),
            "afternoon": r.get("afternoon"),
        }
        for r in records
    ]


@dataclass
class Signal:
    trip_id: str
    action: str
    confidence: float
    best_price_per_person: float | None
    predicted_low_per_person: float | None
    days_to_depart: int
    reasoning: str
    trend: str


def analyze_trip(trip_id: str, morning_ppp: float | None, afternoon_ppp: float | None, depart_date: str) -> Signal:
    history = load_history()
    records = history.get(trip_id, [])
    days_to_depart = (date.fromisoformat(depart_date) - date.today()).days

    # Best current price per person
    candidates = [p for p in [morning_ppp, afternoon_ppp] if p is not None]
    best_ppp = min(candidates) if candidates else None

    if not candidates:
        return Signal(
            trip_id=trip_id, action="WAIT", confidence=0.3,
            best_price_per_person=None, predicted_low_per_person=None,
            days_to_depart=days_to_depart,
            reasoning="No nonstop American flights found for these dates.",
            trend="STABLE",
        )

    if len(records) < 3:
        return Signal(
            trip_id=trip_id, action="WAIT", confidence=0.3,
            best_price_per_person=best_ppp,
            predicted_low_per_person=round(best_ppp * 0.9, 2) if best_ppp else None,
            days_to_depart=days_to_depart,
            reasoning="Still collecting price history — check back in a few days.",
            trend="STABLE",
        )

    # Use best daily price for trend analysis
    best_prices = []
    for r in records[-30:]:
        vals = [v for k, v in r.items() if k in ("morning", "afternoon") and v is not None]
        if vals:
            best_prices.append(min(vals))

    if not best_prices:
        return Signal(
            trip_id=trip_id, action="WAIT", confidence=0.3,
            best_price_per_person=best_ppp, predicted_low_per_person=None,
            days_to_depart=days_to_depart,
            reasoning="Still collecting price history.",
            trend="STABLE",
        )

    arr = np.array(best_prices)
    slope = float(np.polyfit(np.arange(len(arr)), arr, 1)[0])
    trend = "RISING" if slope > 2 else ("FALLING" if slope < -2 else "STABLE")
    avg = float(np.mean(arr))
    std = float(np.std(arr))
    predicted_low = max(avg - std, best_ppp * 0.75) if best_ppp else avg - std

    sweet_spot = 21 <= days_to_depart <= 90
    last_chance = days_to_depart < 14

    if last_chance:
        action, confidence, reasoning = (
            "BUY", 0.88,
            f"Only {days_to_depart}d out — AA nonstop prices spike in the final 2 weeks.",
        )
    elif best_ppp and best_ppp <= predicted_low * 1.02 and sweet_spot:
        action, confidence, reasoning = (
            "BUY", 0.82,
            f"Per-person price is at/near the predicted floor (${predicted_low:.0f}/person) in the ideal window.",
        )
    elif trend == "RISING" and days_to_depart < 45:
        action, confidence, reasoning = (
            "BUY", 0.72,
            f"Prices trending up with {days_to_depart}d left. Book before it climbs further.",
        )
    elif trend == "FALLING" and days_to_depart > 45:
        action, confidence, reasoning = (
            "WAIT", 0.68,
            f"Prices still dropping with {days_to_depart} days of runway. Hold for a better rate.",
        )
    else:
        action, confidence, reasoning = (
            "HOLD", 0.55,
            f"Price near avg (${avg:.0f}/person). No strong signal yet — keep watching.",
        )

    return Signal(
        trip_id=trip_id, action=action, confidence=confidence,
        best_price_per_person=best_ppp,
        predicted_low_per_person=round(predicted_low, 2),
        days_to_depart=days_to_depart, reasoning=reasoning, trend=trend,
    )


def get_all_signals(trips: list[dict], options_map: dict) -> list[dict]:
    signals = []
    for t in trips:
        if not t.get("active"):
            continue
        opts = options_map.get(t["id"], {})
        morning_ppp = opts.get("morning", {}).get("price_per_person")
        afternoon_ppp = opts.get("afternoon", {}).get("price_per_person")
        sig = analyze_trip(t["id"], morning_ppp, afternoon_ppp, t["depart_date"])
        signals.append(asdict(sig))
    return signals
