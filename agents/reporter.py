"""
Reporter Agent — sends email alerts when price drops exceed threshold.
Uses Gmail SMTP with App Password. Tracks last-sent prices to avoid spam.
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

SENT_LOG_PATH = Path(__file__).parent.parent / "data" / "sent_alerts.json"
CONFIG_PATH = Path(__file__).parent.parent / "config.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def load_sent_log() -> dict:
    if not SENT_LOG_PATH.exists():
        return {}
    return json.loads(SENT_LOG_PATH.read_text())


def save_sent_log(log: dict):
    SENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SENT_LOG_PATH.write_text(json.dumps(log, indent=2))


def should_send_alert(trip_id: str, new_price: float, threshold_pct: float) -> tuple[bool, float]:
    log = load_sent_log()
    last = log.get(trip_id, {}).get("price_at_send")
    if last is None:
        return True, 0.0
    drop_pct = ((last - new_price) / last) * 100
    return drop_pct >= threshold_pct, drop_pct


def _build_html(trip: dict, signal: dict, new_price: float, drop_pct: float) -> str:
    action_color = {"BUY": "#22c55e", "HOLD": "#f59e0b", "WAIT": "#3b82f6"}.get(signal["action"], "#6b7280")
    return f"""
<html><body style="font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:24px">
  <h2 style="color:#38bdf8">✈️ Auto — Round-Trip Price Alert</h2>
  <table style="border-collapse:collapse;width:100%;max-width:520px">
    <tr>
      <td style="padding:8px;color:#94a3b8">Trip</td>
      <td style="padding:8px;font-weight:bold">{trip['label']}</td>
    </tr>
    <tr style="background:#1e293b">
      <td style="padding:8px;color:#94a3b8">Route</td>
      <td style="padding:8px">{trip['origin']} ↔ {trip['destination']}</td>
    </tr>
    <tr>
      <td style="padding:8px;color:#94a3b8">Dates</td>
      <td style="padding:8px">{trip['depart_date']} → {trip['return_date']} ({trip['duration_days']} days)</td>
    </tr>
    <tr style="background:#1e293b">
      <td style="padding:8px;color:#94a3b8">Round-Trip Total ({trip['passengers']} pax)</td>
      <td style="padding:8px;font-size:1.4em;font-weight:bold;color:#22c55e">${new_price:.0f}</td>
    </tr>
    <tr>
      <td style="padding:8px;color:#94a3b8">Per Person</td>
      <td style="padding:8px;color:#94a3b8">${new_price / trip['passengers']:.0f}</td>
    </tr>
    <tr style="background:#1e293b">
      <td style="padding:8px;color:#94a3b8">Price Drop</td>
      <td style="padding:8px;color:#22c55e">↓ {drop_pct:.1f}%</td>
    </tr>
    <tr>
      <td style="padding:8px;color:#94a3b8">Signal</td>
      <td style="padding:8px">
        <span style="background:{action_color};color:#fff;padding:4px 12px;border-radius:4px;font-weight:bold">
          {signal['action']}
        </span>
        ({int(signal['confidence']*100)}% confidence)
      </td>
    </tr>
    <tr style="background:#1e293b">
      <td style="padding:8px;color:#94a3b8">Auto says</td>
      <td style="padding:8px;font-style:italic">{signal['reasoning']}</td>
    </tr>
  </table>
  <p style="color:#475569;font-size:0.8em;margin-top:24px">Auto — Autopilot Flight Tracker · Onyx Media Group</p>
</body></html>
"""


def send_alert(trip: dict, signal: dict, new_price: float, drop_pct: float):
    config = load_config()
    gmail_user = os.getenv("GMAIL_USER")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_pass:
        print("[Reporter] GMAIL_USER or GMAIL_APP_PASSWORD not set — skipping email.")
        return

    subject = (
        f"✈️ Auto: {trip['label']} round-trip dropped {drop_pct:.1f}% "
        f"to ${new_price:.0f} — {signal['action']}"
    )
    html = _build_html(trip, signal, new_price, drop_pct)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = ", ".join(config["autopilot"]["alert_emails"])
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_pass)
        server.sendmail(gmail_user, config["autopilot"]["alert_emails"], msg.as_string())

    log = load_sent_log()
    log[trip["id"]] = {"price_at_send": new_price, "sent_at": datetime.utcnow().isoformat()}
    save_sent_log(log)
    print(f"[Reporter] Alert sent for {trip['id']} — ${new_price:.0f} ({drop_pct:.1f}% drop)")


def check_and_alert(trip: dict, signal: dict, options: dict):
    config = load_config()
    threshold = config["autopilot"]["price_drop_threshold_pct"]
    best_ppp = signal.get("best_price_per_person")
    if best_ppp is None:
        return
    # Track alert on per-person basis
    should_send, drop_pct = should_send_alert(trip["id"], best_ppp, threshold)
    if should_send:
        send_alert(trip, signal, best_ppp * trip["passengers"], drop_pct)
