"""
Analyzer Agent — builds price history, detects trends, emits BUY/HOLD/WAIT signals.

Signal logic priority (highest to lowest):
  1. Days to departure (urgency override)
  2. Google price_level ("low" / "typical" / "high") — Google's own 30-day assessment
  3. Route scarcity (few AA nonstops = thin route = prices rise as seats fill)
  4. Our own collected trend (slope of recorded prices)
  5. Position vs. predicted floor
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


def seed_from_google(trip_id: str, google_history_ppp: list[dict]):
    """
    Backfill history from Google's price_history if we have fewer than 5 own data points.
    Google gives ~30 days of price data per response — use it.
    """
    if not google_history_ppp:
        return
    history = load_history()
    own = history.get(trip_id, [])
    if len(own) >= 5:
        return  # we have enough of our own data, don't overwrite

    # Convert Google's blended price to our {ts, morning, afternoon} format
    # We don't know time-of-day, so we store as morning (best approximation)
    seeded = []
    for entry in google_history_ppp:
        seeded.append({
            "ts": entry["ts"],
            "morning": entry["price_per_person"],
            "afternoon": None,
            "source": "google",
        })

    # Merge: keep any own entries, prepend Google seeds, deduplicate by date
    combined = seeded + own
    seen_dates = set()
    deduped = []
    for e in combined:
        d = e["ts"][:10]
        if d not in seen_dates:
            seen_dates.add(d)
            deduped.append(e)

    deduped.sort(key=lambda x: x["ts"])
    history[trip_id] = deduped[-500:]
    save_history(history)
    print(f"[Analyzer] Seeded {len(seeded)} Google history points for {trip_id}")


def record_prices(trip_id: str, morning_ppp: float | None, afternoon_ppp: float | None):
    history = load_history()
    if trip_id not in history:
        history[trip_id] = []
    entry = {"ts": datetime.utcnow().isoformat()}
    if morning_ppp is not None:
        entry["morning"] = morning_ppp
    if afternoon_ppp is not None:
        entry["afternoon"] = afternoon_ppp
    if len(entry) > 1:
        history[trip_id].append(entry)
        history[trip_id] = history[trip_id][-500:]
        save_history(history)


def get_price_chart_data(trip_id: str) -> list[dict]:
    history = load_history()
    return [
        {"ts": r["ts"], "morning": r.get("morning"), "afternoon": r.get("afternoon")}
        for r in history.get(trip_id, [])
    ]


@dataclass
class Signal:
    trip_id: str
    action: str                        # BUY | HOLD | WAIT
    confidence: float
    best_price_per_person: float | None
    predicted_low_per_person: float | None
    typical_range_ppp: list | None     # [low, high] from Google
    price_level: str | None            # "low" | "typical" | "high" from Google
    aa_nonstop_count: int              # how many AA nonstop options exist
    days_to_depart: int
    data_points: int                   # how many history entries we have
    reasoning: str
    trend: str                         # RISING | FALLING | STABLE


def analyze_trip(
    trip_id: str,
    morning_ppp: float | None,
    afternoon_ppp: float | None,
    depart_date: str,
    price_insights: dict | None = None,
    aa_nonstop_count: int = 0,
) -> Signal:
    history = load_history()
    records = history.get(trip_id, [])
    days_to_depart = (date.fromisoformat(depart_date) - date.today()).days

    insights = price_insights or {}
    price_level = insights.get("price_level")        # "low" | "typical" | "high"
    typical_range = insights.get("typical_range_ppp")
    lowest_ppp = insights.get("lowest_ppp")

    candidates = [p for p in [morning_ppp, afternoon_ppp] if p is not None]
    best_ppp = min(candidates) if candidates else None

    # ── No AA nonstop flights found ─────────────────────────────────────────
    if not candidates:
        return Signal(
            trip_id=trip_id, action="WAIT", confidence=0.25,
            best_price_per_person=None, predicted_low_per_person=None,
            typical_range_ppp=typical_range, price_level=price_level,
            aa_nonstop_count=0, days_to_depart=days_to_depart,
            data_points=len(records),
            reasoning="No nonstop American Airlines flights found for these dates. Check back — availability opens closer to departure.",
            trend="STABLE",
        )

    # ── Build price series from history ─────────────────────────────────────
    best_series = []
    for r in records[-45:]:
        vals = [v for k, v in r.items() if k in ("morning", "afternoon") and isinstance(v, (int, float))]
        if vals:
            best_series.append(min(vals))
    data_points = len(records)

    # ── Trend analysis (need ≥5 points) ─────────────────────────────────────
    trend = "STABLE"
    slope = 0.0
    if len(best_series) >= 5:
        arr = np.array(best_series)
        slope = float(np.polyfit(np.arange(len(arr)), arr, 1)[0])
        trend = "RISING" if slope > 1.5 else ("FALLING" if slope < -1.5 else "STABLE")

    # Predicted floor: use Google's lowest if available, else stats
    if lowest_ppp:
        predicted_low = lowest_ppp
    elif best_series:
        arr = np.array(best_series)
        predicted_low = max(float(np.mean(arr) - np.std(arr)), best_ppp * 0.80)
    else:
        predicted_low = best_ppp * 0.85 if best_ppp else None

    # ── Route scarcity factor ────────────────────────────────────────────────
    # Thin route (≤3 AA nonstop options): seats fill fast, prices spike last 6 weeks
    thin_route = aa_nonstop_count <= 3

    # ── Confidence: scales with data quality ────────────────────────────────
    # Google's price_level gives us a strong prior even on day 1
    has_google_signal = price_level in ("low", "typical", "high")
    base_confidence = 0.35 + (min(data_points, 30) / 30) * 0.40  # 0.35 → 0.75 over 30 days
    if has_google_signal:
        base_confidence = min(base_confidence + 0.20, 0.92)       # Google signal adds 20pts

    # ── Decision logic ───────────────────────────────────────────────────────
    last_chance  = days_to_depart < 14
    thin_warning = thin_route and days_to_depart < 56   # under 8 weeks on a thin route
    sweet_spot   = 21 <= days_to_depart <= 90

    if last_chance:
        action = "BUY"
        confidence = min(base_confidence + 0.15, 0.95)
        reasoning = (
            f"Only {days_to_depart} days out — nonstop AA seats are scarce and "
            f"prices spike in the final 2 weeks. Book now."
        )

    elif price_level == "low":
        action = "BUY"
        confidence = min(base_confidence + 0.10, 0.92)
        range_str = f" (typical range: ${typical_range[0]:.0f}–${typical_range[1]:.0f}/person)" if typical_range else ""
        reasoning = (
            f"Google rates this price as LOW{range_str}. "
            f"Current ${best_ppp:.0f}/person is below the typical range — "
            f"{'this is as good as it gets on this thin route.' if thin_route else 'a genuine deal worth locking in.'}"
        )

    elif price_level == "high" and days_to_depart > 45:
        action = "WAIT"
        confidence = min(base_confidence + 0.05, 0.85)
        range_str = f" Typical: ${typical_range[0]:.0f}–${typical_range[1]:.0f}/person." if typical_range else ""
        reasoning = (
            f"Google rates this price as HIGH.{range_str} "
            f"With {days_to_depart} days of runway, hold — prices typically pull back toward the typical range."
        )

    elif thin_warning:
        action = "BUY"
        confidence = min(base_confidence + 0.08, 0.88)
        range_str = f" Typical: ${typical_range[0]:.0f}–${typical_range[1]:.0f}/person." if typical_range else ""
        reasoning = (
            f"Thin route — only {aa_nonstop_count} nonstop AA option(s) found.{range_str} "
            f"With {days_to_depart} days left, seats fill and prices climb. "
            f"At ${best_ppp:.0f}/person this is unlikely to get cheaper."
        )

    elif trend == "RISING" and days_to_depart < 60:
        action = "BUY"
        confidence = min(base_confidence, 0.80)
        reasoning = (
            f"Price trending UP (${slope:+.1f}/person per check) with {days_to_depart} days left. "
            f"Waiting costs money — lock in ${best_ppp:.0f}/person now."
        )

    elif trend == "FALLING" and days_to_depart > 60 and price_level != "low":
        action = "WAIT"
        confidence = min(base_confidence, 0.75)
        reasoning = (
            f"Price trending DOWN with {days_to_depart} days of runway. "
            f"Hold and check again — the floor hasn't been reached yet."
        )

    elif best_ppp and predicted_low and best_ppp <= predicted_low * 1.03 and sweet_spot:
        action = "BUY"
        confidence = min(base_confidence + 0.05, 0.85)
        reasoning = (
            f"Price at or near predicted floor (${predicted_low:.0f}/person). "
            f"In the booking sweet spot at {days_to_depart} days out."
        )

    else:
        action = "HOLD"
        confidence = base_confidence
        google_note = f" Google: {price_level.upper()}." if price_level else ""
        range_str = f" Typical: ${typical_range[0]:.0f}–${typical_range[1]:.0f}/person." if typical_range else ""
        reasoning = (
            f"${best_ppp:.0f}/person, {days_to_depart} days out.{google_note}{range_str} "
            f"No strong signal — watch for a drop below ${predicted_low:.0f}/person." if predicted_low
            else f"${best_ppp:.0f}/person, {days_to_depart} days out.{google_note} Monitoring."
        )

    return Signal(
        trip_id=trip_id,
        action=action,
        confidence=round(confidence, 3),
        best_price_per_person=best_ppp,
        predicted_low_per_person=round(predicted_low, 2) if predicted_low else None,
        typical_range_ppp=typical_range,
        price_level=price_level,
        aa_nonstop_count=aa_nonstop_count,
        days_to_depart=days_to_depart,
        data_points=data_points,
        reasoning=reasoning,
        trend=trend,
    )


def get_all_signals(trips: list[dict], options_map: dict) -> list[dict]:
    signals = []
    for t in trips:
        if not t.get("active"):
            continue
        opts = options_map.get(t["id"], {})
        morning_ppp = opts.get("morning", {}).get("price_per_person")
        afternoon_ppp = opts.get("afternoon", {}).get("price_per_person")
        price_insights = opts.get("price_insights", {})
        aa_count = opts.get("aa_nonstop_count", 0)
        sig = analyze_trip(
            t["id"], morning_ppp, afternoon_ppp, t["depart_date"],
            price_insights=price_insights,
            aa_nonstop_count=aa_count,
        )
        signals.append(asdict(sig))
    return signals
