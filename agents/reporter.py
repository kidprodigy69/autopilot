"""
Reporter Agent — sends price-drop alerts with AA booking links.
Tracks a per-trip price baseline. First poll sets baseline (no alert).
Every subsequent poll: email if price dropped ≥ threshold% from baseline.
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


def _flight_rows_html(morning: list, afternoon: list) -> str:
    rows = ""
    for slot_label, flights in [("☀️ Morning", morning), ("🌇 Afternoon", afternoon)]:
        for i, f in enumerate(flights[:3]):
            fn = f.get("flight_number", "—")
            dep = f.get("depart_time", "—")
            arr = f.get("arrive_time", "—")
            ppp = f.get("price_per_person", 0)
            total = f.get("price_total", 0)
            cheapest = i == 0 and len(flights) > 1
            bg = "#0f2a1a" if cheapest else "#1e293b"
            badge = '<span style="background:#22c55e;color:#fff;font-size:0.7em;padding:1px 5px;border-radius:3px;margin-left:4px">lowest</span>' if cheapest else ""
            rows += f"""
<tr style="background:{bg}">
  <td style="padding:8px 10px;color:#94a3b8;font-size:0.82em;white-space:nowrap">{slot_label if i == 0 else ""}</td>
  <td style="padding:8px 10px;font-family:monospace;font-weight:bold;color:#e2e8f0">{fn}{badge}</td>
  <td style="padding:8px 10px;color:#cbd5e1;white-space:nowrap">{dep} → {arr}</td>
  <td style="padding:8px 10px;text-align:right;white-space:nowrap">
    <strong style="color:#22c55e">${ppp:.0f}</strong><span style="color:#475569;font-size:0.85em">/pp</span>
    <br><span style="color:#475569;font-size:0.8em">${total:.0f} total</span>
  </td>
</tr>"""
    return rows


def _build_html(trip: dict, signal: dict, options: dict, new_ppp: float, drop_pct: float) -> str:
    action = signal.get("action", "?")
    action_color = {"BUY": "#22c55e", "HOLD": "#f59e0b", "WAIT": "#3b82f6"}.get(action, "#6b7280")
    total = new_ppp * trip["passengers"]
    morning = options.get("morning", [])
    afternoon = options.get("afternoon", [])
    flight_rows = _flight_rows_html(morning, afternoon)
    aa_url = options.get("aa_booking_url", "https://www.aa.com")
    level = (signal.get("price_level") or "").upper()
    level_color = {"LOW": "#22c55e", "TYPICAL": "#f59e0b", "HIGH": "#ef4444"}.get(level, "#94a3b8")
    typical = signal.get("typical_range_ppp")
    typical_str = f"${typical[0]:.0f}–${typical[1]:.0f}/pp" if typical else ""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0b1628;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0b1628;padding:24px 0">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#111827;border-radius:12px;overflow:hidden;border:1px solid #1e3a5f">

  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#0c2340,#0f3460);padding:24px 28px">
    <table width="100%"><tr>
      <td>
        <div style="font-size:0.75em;color:#38bdf8;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px">Autopilot · Onyx Media Group</div>
        <div style="font-size:1.5em;font-weight:800;color:#fff">✈️ Price Drop Detected</div>
      </td>
      <td align="right">
        <div style="background:{action_color};color:#fff;font-weight:900;font-size:1.1em;padding:8px 16px;border-radius:8px;display:inline-block">{action}</div>
      </td>
    </tr></table>
  </td></tr>

  <!-- Trip summary -->
  <tr><td style="padding:20px 28px 0">
    <table width="100%" style="border-collapse:collapse">
      <tr>
        <td style="padding:10px 0;border-bottom:1px solid #1e293b;color:#64748b;font-size:0.85em;width:130px">Trip</td>
        <td style="padding:10px 0;border-bottom:1px solid #1e293b;font-weight:600;color:#e2e8f0">{trip['label']}</td>
      </tr>
      <tr>
        <td style="padding:10px 0;border-bottom:1px solid #1e293b;color:#64748b;font-size:0.85em">Route</td>
        <td style="padding:10px 0;border-bottom:1px solid #1e293b;color:#e2e8f0">{trip['origin']} ↔ {trip['destination']} · Nonstop · American Airlines</td>
      </tr>
      <tr>
        <td style="padding:10px 0;border-bottom:1px solid #1e293b;color:#64748b;font-size:0.85em">Dates</td>
        <td style="padding:10px 0;border-bottom:1px solid #1e293b;color:#e2e8f0">{trip['depart_date']} → {trip['return_date']} ({trip['duration_days']} days)</td>
      </tr>
      <tr>
        <td style="padding:10px 0;border-bottom:1px solid #1e293b;color:#64748b;font-size:0.85em">New Price</td>
        <td style="padding:10px 0;border-bottom:1px solid #1e293b">
          <span style="font-size:1.6em;font-weight:900;color:#22c55e">${new_ppp:.0f}<span style="font-size:0.6em;font-weight:400;color:#6b7280">/person</span></span>
          <span style="color:#94a3b8;font-size:0.9em;margin-left:8px">${total:.0f} total for {trip['passengers']} passengers</span>
        </td>
      </tr>
      <tr>
        <td style="padding:10px 0;border-bottom:1px solid #1e293b;color:#64748b;font-size:0.85em">Price Drop</td>
        <td style="padding:10px 0;border-bottom:1px solid #1e293b;color:#22c55e;font-weight:700;font-size:1.1em">↓ {drop_pct:.1f}% from last check</td>
      </tr>
      {"" if not level else f'''<tr>
        <td style="padding:10px 0;border-bottom:1px solid #1e293b;color:#64748b;font-size:0.85em">Google rates this</td>
        <td style="padding:10px 0;border-bottom:1px solid #1e293b">
          <span style="color:{level_color};font-weight:700">{level}</span>
          {"&nbsp;·&nbsp;<span style='color:#475569;font-size:0.85em'>Typical " + typical_str + "</span>" if typical_str else ""}
        </td>
      </tr>'''}
    </table>
  </td></tr>

  <!-- Available flights -->
  {"" if not flight_rows else f'''
  <tr><td style="padding:20px 28px 0">
    <div style="font-size:0.7em;font-weight:700;color:#475569;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px">Available Nonstop Flights</div>
    <table width="100%" style="border-collapse:collapse;border-radius:8px;overflow:hidden;font-size:0.88em">
      <tr style="background:#0f172a">
        <td style="padding:6px 10px;color:#475569;font-size:0.8em">Slot</td>
        <td style="padding:6px 10px;color:#475569;font-size:0.8em">Flight</td>
        <td style="padding:6px 10px;color:#475569;font-size:0.8em">Times</td>
        <td style="padding:6px 10px;color:#475569;font-size:0.8em;text-align:right">Price</td>
      </tr>
      {flight_rows}
    </table>
  </td></tr>
  '''}

  <!-- Book on AA button -->
  <tr><td style="padding:24px 28px">
    <table width="100%"><tr>
      <td align="center">
        <a href="{aa_url}" target="_blank"
           style="display:inline-block;background:#004b87;color:#fff;font-weight:700;font-size:1em;
                  padding:14px 32px;border-radius:8px;text-decoration:none;letter-spacing:0.02em;
                  border:2px solid #0073cf">
          🛫 Book on American Airlines
        </a>
        <div style="color:#334155;font-size:0.75em;margin-top:8px">
          Opens aa.com with {trip['origin']} ↔ {trip['destination']} · {trip['depart_date']} pre-filled
        </div>
      </td>
    </tr></table>
  </td></tr>

  <!-- Auto reasoning -->
  <tr><td style="padding:0 28px 24px">
    <div style="background:#0f172a;border-left:3px solid #1e40af;border-radius:0 8px 8px 0;padding:14px 16px">
      <div style="color:#38bdf8;font-size:0.75em;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px">Auto's Reasoning</div>
      <div style="color:#94a3b8;font-size:0.88em;line-height:1.5">{signal.get('reasoning','—')}</div>
    </div>
  </td></tr>

  <!-- Footer -->
  <tr><td style="background:#0b1628;padding:16px 28px;text-align:center;border-top:1px solid #1e293b">
    <div style="color:#1e3a5f;font-size:0.75em">
      Auto checks prices 4× daily · <a href="https://autopilot-onyx.vercel.app" style="color:#1e40af;text-decoration:none">View Dashboard</a>
    </div>
  </td></tr>

</table>
</td></tr></table>
</body></html>"""


def send_alert(trip: dict, signal: dict, options: dict, new_ppp: float, drop_pct: float):
    config = load_config()
    gmail_user = os.getenv("GMAIL_USER")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD")
    if not gmail_user or not gmail_pass:
        print("[Reporter] Gmail credentials not set — skipping email.")
        return

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
        print(f"[Reporter] {trip_id}: ${best_ppp:.0f}/pp — down {drop_pct:.1f}% (threshold {threshold}%)")
    else:
        print(f"[Reporter] {trip_id}: ${best_ppp:.0f}/pp — up {abs(drop_pct):.1f}% from baseline")
