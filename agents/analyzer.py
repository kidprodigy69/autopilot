"""
Analyzer Agent — reads price history, detects patterns, predicts best buy windows,
and emits BUY / HOLD / WAIT signals per mission.
"""
import json
import numpy as np
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional
from dataclasses import dataclass, asdict

HISTORY_PATH = Path(__file__).parent.parent / "data" / "price_history.json"


def load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {}
    return json.loads(HISTORY_PATH.read_text())


def save_history(history: dict):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2))


def record_price(mission_id: str, price: float, airline: str):
    history = load_history()
    if mission_id not in history:
        history[mission_id] = []
    history[mission_id].append({
        "ts": datetime.utcnow().isoformat(),
        "price": price,
        "airline": airline,
    })
    # Keep last 500 data points per mission
    history[mission_id] = history[mission_id][-500:]
    save_history(history)


@dataclass
class Signal:
    mission_id: str
    action: str          # BUY | HOLD | WAIT
    confidence: float    # 0.0 – 1.0
    current_price: float
    predicted_low: float
    predicted_high: float
    days_to_depart: int
    reasoning: str
    trend: str           # RISING | FALLING | STABLE


def analyze_mission(mission_id: str, current_price: float, depart_date: str) -> Signal:
    history = load_history()
    records = history.get(mission_id, [])

    depart = date.fromisoformat(depart_date)
    days_to_depart = (depart - date.today()).days

    if len(records) < 3:
        return Signal(
            mission_id=mission_id,
            action="WAIT",
            confidence=0.3,
            current_price=current_price,
            predicted_low=current_price * 0.9,
            predicted_high=current_price * 1.1,
            days_to_depart=days_to_depart,
            reasoning="Insufficient price history — collecting data.",
            trend="STABLE",
        )

    prices = [r["price"] for r in records[-30:]]
    arr = np.array(prices)

    # Linear trend
    x = np.arange(len(arr))
    slope = np.polyfit(x, arr, 1)[0]
    trend = "RISING" if slope > 1 else ("FALLING" if slope < -1 else "STABLE")

    avg = float(np.mean(arr))
    std = float(np.std(arr))
    predicted_low = max(avg - std, current_price * 0.7)
    predicted_high = avg + std

    # Booking window heuristic (domestic USA)
    sweet_spot = 21 <= days_to_depart <= 90
    last_chance = days_to_depart < 14

    if last_chance:
        action, confidence, reasoning = (
            "BUY",
            0.85,
            f"Only {days_to_depart}d until departure — prices typically spike in final 2 weeks.",
        )
    elif current_price <= predicted_low * 1.02 and sweet_spot:
        action, confidence, reasoning = (
            "BUY",
            0.80,
            f"Price is at/near predicted floor ({predicted_low:.0f}) in the optimal booking window.",
        )
    elif trend == "RISING" and days_to_depart < 45:
        action, confidence, reasoning = (
            "BUY",
            0.70,
            f"Prices trending up ({slope:+.1f}/check) with {days_to_depart}d left — don't wait.",
        )
    elif trend == "FALLING" and days_to_depart > 45:
        action, confidence, reasoning = (
            "WAIT",
            0.65,
            f"Prices still falling with {days_to_depart}d runway — hold for a better price.",
        )
    else:
        action, confidence, reasoning = (
            "HOLD",
            0.55,
            f"Price within 5% of avg (${avg:.0f}). No strong signal yet.",
        )

    return Signal(
        mission_id=mission_id,
        action=action,
        confidence=confidence,
        current_price=current_price,
        predicted_low=round(predicted_low, 2),
        predicted_high=round(predicted_high, 2),
        days_to_depart=days_to_depart,
        reasoning=reasoning,
        trend=trend,
    )


def get_price_chart_data(mission_id: str) -> list[dict]:
    history = load_history()
    records = history.get(mission_id, [])
    return [{"ts": r["ts"], "price": r["price"]} for r in records]


def get_all_signals(missions: list[dict], current_prices: dict) -> list[dict]:
    signals = []
    for m in missions:
        if not m.get("active"):
            continue
        best_price = current_prices.get(m["id"])
        if best_price is None:
            continue
        sig = analyze_mission(m["id"], best_price, m["depart_date"])
        signals.append(asdict(sig))
    return signals
