"""
Analyzer Agent — reads round-trip price history, detects patterns,
and emits BUY / HOLD / WAIT signals per trip.
"""
import json
import numpy as np
from pathlib import Path
from datetime import datetime, date, timedelta
from dataclasses import dataclass, asdict

HISTORY_PATH = Path(__file__).parent.parent / "data" / "price_history.json"


def load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {}
    return json.loads(HISTORY_PATH.read_text())


def save_history(history: dict):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2))


def record_price(trip_id: str, price: float, airline: str):
    history = load_history()
    if trip_id not in history:
        history[trip_id] = []
    history[trip_id].append({
        "ts": datetime.utcnow().isoformat(),
        "price": price,
        "airline": airline,
    })
    history[trip_id] = history[trip_id][-500:]
    save_history(history)


@dataclass
class Signal:
    trip_id: str
    action: str          # BUY | HOLD | WAIT
    confidence: float
    current_price: float
    predicted_low: float
    predicted_high: float
    days_to_depart: int
    reasoning: str
    trend: str           # RISING | FALLING | STABLE


def analyze_trip(trip_id: str, current_price: float, depart_date: str) -> Signal:
    history = load_history()
    records = history.get(trip_id, [])

    days_to_depart = (date.fromisoformat(depart_date) - date.today()).days

    if len(records) < 3:
        return Signal(
            trip_id=trip_id,
            action="WAIT",
            confidence=0.3,
            current_price=current_price,
            predicted_low=round(current_price * 0.9, 2),
            predicted_high=round(current_price * 1.1, 2),
            days_to_depart=days_to_depart,
            reasoning="Collecting price history — check back in a few days for a signal.",
            trend="STABLE",
        )

    prices = [r["price"] for r in records[-30:]]
    arr = np.array(prices)
    slope = float(np.polyfit(np.arange(len(arr)), arr, 1)[0])
    trend = "RISING" if slope > 2 else ("FALLING" if slope < -2 else "STABLE")

    avg = float(np.mean(arr))
    std = float(np.std(arr))
    predicted_low = max(avg - std, current_price * 0.75)
    predicted_high = avg + std

    sweet_spot = 21 <= days_to_depart <= 90
    last_chance = days_to_depart < 14

    if last_chance:
        action, confidence, reasoning = (
            "BUY", 0.88,
            f"Only {days_to_depart} days out — round-trip prices spike in the final 2 weeks.",
        )
    elif current_price <= predicted_low * 1.02 and sweet_spot:
        action, confidence, reasoning = (
            "BUY", 0.82,
            f"Round-trip total is at/near the predicted floor (${predicted_low:.0f}) in the ideal booking window.",
        )
    elif trend == "RISING" and days_to_depart < 45:
        action, confidence, reasoning = (
            "BUY", 0.72,
            f"Prices trending up (${slope:+.0f}/check) with only {days_to_depart} days left. Don't wait.",
        )
    elif trend == "FALLING" and days_to_depart > 45:
        action, confidence, reasoning = (
            "WAIT", 0.68,
            f"Prices still falling with {days_to_depart} days of runway. Hold for a better total.",
        )
    else:
        action, confidence, reasoning = (
            "HOLD", 0.55,
            f"Round-trip total within range of avg (${avg:.0f}). No strong signal yet.",
        )

    return Signal(
        trip_id=trip_id,
        action=action,
        confidence=confidence,
        current_price=current_price,
        predicted_low=round(predicted_low, 2),
        predicted_high=round(predicted_high, 2),
        days_to_depart=days_to_depart,
        reasoning=reasoning,
        trend=trend,
    )


def get_price_chart_data(trip_id: str) -> list[dict]:
    history = load_history()
    records = history.get(trip_id, [])
    return [{"ts": r["ts"], "price": r["price"]} for r in records]


def get_all_signals(trips: list[dict], current_prices: dict) -> list[dict]:
    signals = []
    for t in trips:
        if not t.get("active"):
            continue
        price = current_prices.get(t["id"])
        if price is None:
            continue
        sig = analyze_trip(t["id"], price, t["depart_date"])
        signals.append(asdict(sig))
    return signals
