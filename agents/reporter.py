"""
Reporter Agent — sends email alerts when price drops ≥ threshold.
Tracks a price baseline per trip. First poll sets the baseline (no alert).
Every subsequent poll: alert if current price dropped ≥ threshold% from baseline.
Baseline only updates downward (we track the last price we alerted on, not all-time high).
"""
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASELINE_PATH = Path(__file__).parent.parent / "data" / "price_baselines.json"
CONFIG_PATH = Path(__file__).parent.parent / "config.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def load_baselines() -> dict:
    if not BASELINE_PATH.exists():
        return {}
    return json.loads(BASELINE_PATH.read_text())


def save_baselines(data: dict):
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(data, indent=2))


def _build_html(trip: dict, signal: dict, options: dict, new_ppp: float, drop_pct: float) -> str:
    action_color = {"BUY": "#22c55e", "HOLD": "#f59e0b", "WAIT": "#3b82f6"}.get(signal.get("action", ""), "#6b7280")
    total = new_ppp * trip["passengers"]

    # Best flights for email
    morning = options.get("morning", [])
    afternoon = options.get("afternoon", [])
    flight_rows = ""
    for slot_label, slot_flights in [("Morning", morning), ("Afternoon", afternoon)]:
        for f in slot_flights[:2]:  # top 2 per slot
            flight_rows += f"""
    <tr>
      <td style="padding:6px 8px;color:#94a3b8">{slot_label}</td>
      <td style="padding:6px 8px;font-family:monospace">{f.get('flight_number','—')}</td>
      <td style="padding:6px 8px">{f.get('depart_time','—')} → {f.get('arrive_time','—')}</td>
      <td style="padding:6px 8px;font-weight:bold;color:#22c55e">${f.get('price_per_person',0):.0f}/pp</td>
    </tr>"""

    return f"""
<html><body style="font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:24px;max-width:600px">
  <div style="border-bottom:1px solid #1e3a5f;padding-bottom:12px;margin-bottom:20px">
    <h2 style="color:#38bdf8;margin:0">✈️ Auto — Price Drop Alert</h2>
    <p style="color:#475569;margin:4px 0 0">Autopilot · Onyx Media Group</p>
  </div>

  <table style="border-collapse:collapse;width:100%;margin-bottom:20px">
    <tr><td style="padding:8px;color:#94a3b8;width:140px">Trip</td>
        <td style="padding:8px;font-weight:bold">{trip['label']}</td></tr>
    <tr style="background:#1e293b">
      <td style="padding:8px;color:#94a3b8">Route</td>
      <td style="padding:8px">{trip['origin']} ↔ {trip['destination']} · Nonstop AA</td></tr>
    <tr><td style="padding:8px;color:#94a3b8">Dates</td>
        <td style="padding:8px">{trip['depart_date']} → {trip['return_date']} ({trip['duration_days']} days)</td></tr>
    <tr style="background:#1e293b">
      <td style="padding:8px;color:#94a3b8">New Price</td>
      <td style="padding:8px;font-size:1.4em;font-weight:bold;color:#22c55e">${new_ppp:.0f}/person · ${total:.0f} total</td></tr>
    <tr><td style="padding:8px;color:#94a3b8">Price Drop</td>
        <td style="padding:8px;color:#22c55e;font-weight:bold">↓ {drop_pct:.1f}%</td></tr>
    <tr style="background:#1e293b">
      <td style="padding:8px;color:#94a3b8">Signal</td>
      <td style="padding:8px">
        <span style="background:{action_color};color:#fff;padding:3px 10px;border-radius:4px;font-weight:bold">
          {signal.get('action','?')}
        </span>
        {f"· Google: {signal.get('price_level','').upper()}" if signal.get('price_level') else ""}
      </td></tr>
  </table>

  {"<h3 style='color:#94a3b8;font-size:0.9em;margin-bottom:8px'>AVAILABLE FLIGHTS</h3><table style='border-collapse:collapse;width:100%;font-size:0.85em'>" + flight_rows + "</table>" if flight_rows else ""}

  <div style="background:#1e293b;border-radius:8px;padding:12px;margin-top:16px">
    <p style="color:#94a3b8;margin:0;font-style:italic;font-size:0.9em">
      <strong style="color:#38bdf8">Auto says:</strong> {signal.get('reasoning','—')}
    </p>
  </div>

  <p style="color:#334155;font-size:0.75em;margin-top:20px">
    Auto checks prices 4x daily · autopilot-onyx.vercel.app
  </p>
</body></html>
"""


def send_alert(trip: dict, signal: dict, options: dict, new_ppp: float, drop_pct: float):
    config = load_config()
    gmail_user = os.getenv("GMAIL_USER")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_pass:
        print("[Reporter] GMAIL credentials not set — skipping email.")
        return

    total = new_ppp * trip["passengers"]
    subject = f"✈️ Auto: {trip['label']} dropped {drop_pct:.1f}% → ${new_ppp:.0f}/person — {signal.get('action','?')}"
    html = _build_html(trip, signal, options, new_ppp, drop_pct)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = ", ".join(config["autopilot"]["alert_emails"])
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, config["autopilot"]["alert_emails"], msg.as_string())
        print(f"[Reporter] Alert sent for {trip['id']} — ${new_ppp:.0f}/pp ({drop_pct:.1f}% drop)")
    except Exception as e:
        print(f"[Reporter] Email send failed: {e}")


def check_and_alert(trip: dict, signal: dict, options: dict):
    """
    Compare current best price to stored baseline.
    First run: set baseline, no alert.
    Subsequent runs: alert if dropped ≥ threshold% from baseline.
    Baseline updates to new price after an alert so next alert is relative to the new level.
    """
    config = load_config()
    threshold = config["autopilot"]["price_drop_threshold_pct"]
    trip_id = trip["id"]

    best_ppp = signal.get("best_price_per_person")
    if best_ppp is None:
        return

    baselines = load_baselines()
    entry = baselines.get(trip_id, {})
    baseline_ppp = entry.get("baseline_ppp")

    if baseline_ppp is None:
        # First time seeing this trip — set baseline, no alert
        baselines[trip_id] = {
            "baseline_ppp": best_ppp,
            "set_at": datetime.utcnow().isoformat(),
            "alerts_sent": 0,
        }
        save_baselines(baselines)
        print(f"[Reporter] Baseline set for {trip_id}: ${best_ppp:.0f}/person")
        return

    drop_pct = ((baseline_ppp - best_ppp) / baseline_ppp) * 100

    if drop_pct >= threshold:
        send_alert(trip, signal, options, best_ppp, drop_pct)
        baselines[trip_id]["baseline_ppp"] = best_ppp
        baselines[trip_id]["last_alert_at"] = datetime.utcnow().isoformat()
        baselines[trip_id]["alerts_sent"] = entry.get("alerts_sent", 0) + 1
        save_baselines(baselines)
    elif drop_pct > 0:
        print(f"[Reporter] {trip_id}: ${best_ppp:.0f}/pp, down {drop_pct:.1f}% from baseline ${baseline_ppp:.0f} — below {threshold}% threshold")
    elif drop_pct < 0:
        print(f"[Reporter] {trip_id}: ${best_ppp:.0f}/pp, up {abs(drop_pct):.1f}% from baseline ${baseline_ppp:.0f}")
