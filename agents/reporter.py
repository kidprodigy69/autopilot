"""
Reporter Agent — two email types:
1. STATUS UPDATE: sent at every poll cycle (4x/day) covering all trips.
2. DROP ALERT: sent additionally whenever a trip drops ≥ threshold%.
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
CONFIG_PATH   = Path(__file__).parent.parent / "config.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def load_baselines() -> dict:
    if not BASELINE_PATH.exists():
        return {}
    return json.loads(BASELINE_PATH.read_text())


def save_baselines(data: dict):
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(data, indent=2))


def _send(subject: str, html: str):
    """Send an email to all alert addresses. Silently skips if credentials missing."""
    config = load_config()
    gmail_user = os.getenv("GMAIL_USER")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD")
    if not gmail_user or not gmail_pass:
        print("[Reporter] Gmail credentials not set — skipping email.")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = gmail_user
    msg["To"]      = ", ".join(config["autopilot"]["alert_emails"])
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, config["autopilot"]["alert_emails"], msg.as_string())
        print(f"[Reporter] Email sent: {subject[:60]}")
    except Exception as e:
        print(f"[Reporter] Email send failed: {e}")


# ── Shared HTML helpers ───────────────────────────────────────────────────────

_HEADER = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0b1628;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0b1628;padding:24px 0">
<tr><td align="center">
<table width="620" cellpadding="0" cellspacing="0" style="background:#111827;border-radius:12px;overflow:hidden;border:1px solid #1e3a5f">"""

_FOOTER = """
  <tr><td style="background:#0a1222;padding:14px 28px;text-align:center;border-top:1px solid #1e293b">
    <div style="color:#1e3a5f;font-size:0.75em">
      Auto checks prices 4× daily (6am · noon · 6pm · midnight EDT) ·
      <a href="https://autopilot-onyx.vercel.app" style="color:#1e40af;text-decoration:none">View Dashboard</a>
    </div>
    <div style="color:#1e2a3a;font-size:0.7em;margin-top:4px">
      Prices from last Auto check — confirm live fare on Kayak before booking
    </div>
  </td></tr>
</table></td></tr></table>
</body></html>"""


def _action_badge(action: str) -> str:
    color = {"BUY": "#22c55e", "HOLD": "#f59e0b", "WAIT": "#3b82f6"}.get(action, "#6b7280")
    return f'<span style="background:{color};color:#fff;font-weight:900;font-size:0.9em;padding:4px 12px;border-radius:6px;display:inline-block">{action}</span>'


def _flight_rows_html(morning: list, afternoon: list) -> str:
    rows = ""
    for slot_label, flights in [("☀️ Morning", morning), ("🌇 Afternoon", afternoon)]:
        for i, f in enumerate(flights[:3]):
            fn    = f.get("flight_number", "—")
            dep   = f.get("depart_time", "—")
            arr   = f.get("arrive_time", "—")
            ppp   = f.get("price_per_person", 0)
            total = f.get("price_total", 0)
            first = i == 0 and len(flights) > 1
            bg    = "#0d2218" if first else "#1a2332"
            badge = ' <span style="background:#22c55e;color:#fff;font-size:0.68em;padding:1px 5px;border-radius:3px">low</span>' if first else ""
            rows += f"""
<tr style="background:{bg}">
  <td style="padding:7px 10px;color:#64748b;font-size:0.8em;white-space:nowrap">{slot_label if i == 0 else ""}</td>
  <td style="padding:7px 10px;font-family:monospace;font-weight:bold;color:#e2e8f0;white-space:nowrap">{fn}{badge}</td>
  <td style="padding:7px 10px;color:#94a3b8;white-space:nowrap;font-size:0.88em">{dep} → {arr}</td>
  <td style="padding:7px 10px;text-align:right;white-space:nowrap">
    <strong style="color:#f0fdf4">${ppp:.0f}</strong><span style="color:#475569;font-size:0.82em">/pp</span>
    <span style="color:#334155;font-size:0.78em;margin-left:4px">${total:.0f} total</span>
  </td>
</tr>"""
    return rows


def _kayak_button(url: str, origin: str, dest: str) -> str:
    if not url:
        return ""
    return f"""
  <tr><td style="padding:20px 28px 0;text-align:center">
    <a href="{url}" target="_blank"
       style="display:inline-block;background:#ff690f;color:#fff;font-weight:700;font-size:0.95em;
              padding:12px 28px;border-radius:8px;text-decoration:none;letter-spacing:0.02em">
      🔍 Search Kayak — {origin} ↔ {dest}
    </a>
    <div style="color:#334155;font-size:0.72em;margin-top:6px">
      Nonstop · American Airlines only · shows live fare → click "Book on American.com"
    </div>
  </td></tr>"""


# ── Trip block used in status email ──────────────────────────────────────────

def _trip_status_block(trip: dict, signal: dict, options: dict, drop_pct: float | None = None) -> str:
    action     = signal.get("action", "?")
    best_ppp   = signal.get("best_price_per_person")
    days       = signal.get("days_to_depart", 0)
    reasoning  = signal.get("reasoning", "")
    level      = (signal.get("price_level") or "").upper()
    level_color = {"LOW": "#22c55e", "TYPICAL": "#f59e0b", "HIGH": "#ef4444"}.get(level, "#94a3b8")
    morning    = options.get("morning", [])
    afternoon  = options.get("afternoon", [])
    aa_url     = options.get("aa_booking_url", "")
    flight_rows = _flight_rows_html(morning, afternoon)

    drop_banner = ""
    if drop_pct is not None and drop_pct >= 0:
        drop_banner = f"""
  <tr><td style="padding:0 28px">
    <div style="background:#052e16;border:1px solid #166534;border-radius:8px;padding:10px 14px;
                color:#4ade80;font-weight:700;font-size:0.95em;text-align:center">
      ↓ Price dropped {drop_pct:.1f}% — ${best_ppp:.0f}/pp
    </div>
  </td></tr>"""

    price_cell = f"${best_ppp:.0f}/pp · ${best_ppp * trip['passengers']:.0f} total" if best_ppp else "—"

    return f"""
  <!-- Trip: {trip['label']} -->
  <tr><td style="padding:20px 28px 0">
    <table width="100%" style="border-collapse:collapse">
      <tr>
        <td style="padding:0 0 12px">
          <div style="font-size:0.7em;color:#38bdf8;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:2px">
            {trip['origin']} ↔ {trip['destination']} · {trip['depart_date']} → {trip['return_date']} · {days}d away
          </div>
          <div style="font-size:1.15em;font-weight:800;color:#fff">{trip['label']}</div>
        </td>
        <td style="text-align:right;vertical-align:top;padding-top:4px">
          {_action_badge(action)}
          {"&nbsp;" + f'<span style="background:{level_color};color:#000;font-size:0.72em;font-weight:700;padding:3px 8px;border-radius:4px">{level}</span>' if level else ""}
        </td>
      </tr>
    </table>
  </td></tr>
{drop_banner}
  <!-- Flights table -->
  {"" if not flight_rows else f'''
  <tr><td style="padding:10px 28px 0">
    <table width="100%" style="border-collapse:collapse;border-radius:6px;overflow:hidden;font-size:0.87em;border:1px solid #1e293b">
      <tr style="background:#0f172a">
        <td style="padding:5px 10px;color:#475569;font-size:0.78em">Slot</td>
        <td style="padding:5px 10px;color:#475569;font-size:0.78em">Flight</td>
        <td style="padding:5px 10px;color:#475569;font-size:0.78em">Times</td>
        <td style="padding:5px 10px;color:#475569;font-size:0.78em;text-align:right">Price</td>
      </tr>
      {flight_rows}
    </table>
  </td></tr>'''}
  <!-- Reasoning -->
  {"" if not reasoning else f'''
  <tr><td style="padding:10px 28px 0">
    <div style="background:#0f172a;border-left:3px solid #1e40af;padding:10px 14px;border-radius:0 6px 6px 0">
      <span style="color:#38bdf8;font-size:0.73em;font-weight:700;text-transform:uppercase;letter-spacing:0.07em">Auto: </span>
      <span style="color:#94a3b8;font-size:0.85em;line-height:1.5">{reasoning}</span>
    </div>
  </td></tr>'''}
  {_kayak_button(aa_url, trip['origin'], trip['destination'])}
  <tr><td style="padding:0 28px 8px"><hr style="border:none;border-top:1px solid #1e293b;margin:20px 0 0"></td></tr>"""


# ── 1. STATUS UPDATE — fires every poll cycle ─────────────────────────────────

def send_status_update(trips: list, signals_map: dict, options_map: dict, drop_trips: list | None = None):
    """
    Send one combined status email covering all active trips.
    drop_trips: list of trip_ids that had a price drop this cycle (highlighted).
    """
    now_utc = datetime.utcnow()
    hour_edt = (now_utc.hour - 4) % 24
    slot_labels = {6: "6am", 12: "noon", 18: "6pm", 0: "midnight"}
    slot = slot_labels.get(hour_edt, f"{hour_edt:02d}:00") + " EDT"
    drop_note = " 🔴 PRICE DROP" if drop_trips else ""

    subject = f"✈️ Auto — {slot} Price Check{drop_note}"

    trip_blocks = ""
    for trip in trips:
        tid = trip["id"]
        sig  = signals_map.get(tid, {})
        opts = options_map.get(tid, {})
        drop_pct = drop_trips.get(tid) if isinstance(drop_trips, dict) else None
        trip_blocks += _trip_status_block(trip, sig, opts, drop_pct)

    html = _HEADER + f"""
  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#0c2340,#0f3460);padding:20px 28px">
    <table width="100%"><tr>
      <td>
        <div style="font-size:0.72em;color:#38bdf8;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:3px">Autopilot · Onyx Media Group</div>
        <div style="font-size:1.3em;font-weight:800;color:#fff">✈️ {slot} Price Check</div>
      </td>
      <td align="right" style="color:#475569;font-size:0.78em;white-space:nowrap">
        {now_utc.strftime('%b %d, %Y %H:%M UTC')}
      </td>
    </tr></table>
  </td></tr>
{trip_blocks}""" + _FOOTER

    _send(subject, html)


# ── 2. DROP ALERT — fires additionally on ≥ threshold% drop ──────────────────

def _drop_alert_html(trip: dict, signal: dict, options: dict, new_ppp: float, drop_pct: float) -> str:
    action      = signal.get("action", "?")
    action_color = {"BUY": "#22c55e", "HOLD": "#f59e0b", "WAIT": "#3b82f6"}.get(action, "#6b7280")
    total       = new_ppp * trip["passengers"]
    morning     = options.get("morning", [])
    afternoon   = options.get("afternoon", [])
    flight_rows = _flight_rows_html(morning, afternoon)
    aa_url      = options.get("aa_booking_url", "")
    level       = (signal.get("price_level") or "").upper()
    level_color = {"LOW": "#22c55e", "TYPICAL": "#f59e0b", "HIGH": "#ef4444"}.get(level, "#94a3b8")
    typical     = signal.get("typical_range_ppp")
    typical_str = f"${typical[0]:.0f}–${typical[1]:.0f}/pp" if typical else ""

    return _HEADER + f"""
  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#1a0a00,#3d1200);padding:24px 28px">
    <table width="100%"><tr>
      <td>
        <div style="font-size:0.75em;color:#fb923c;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px">Autopilot · Price Alert</div>
        <div style="font-size:1.5em;font-weight:800;color:#fff">🔴 Price Drop — {trip['label']}</div>
      </td>
      <td align="right">
        <div style="background:{action_color};color:#fff;font-weight:900;font-size:1.1em;padding:8px 16px;border-radius:8px">{action}</div>
      </td>
    </tr></table>
  </td></tr>

  <!-- Drop highlight -->
  <tr><td style="padding:20px 28px 0">
    <div style="background:#052e16;border:1px solid #166534;border-radius:10px;padding:16px 20px;text-align:center">
      <div style="font-size:2em;font-weight:900;color:#4ade80">${new_ppp:.0f}<span style="font-size:0.45em;font-weight:400;color:#6b7280">/person</span></div>
      <div style="color:#22c55e;font-weight:700;font-size:1.05em;margin-top:4px">↓ {drop_pct:.1f}% price drop</div>
      <div style="color:#64748b;font-size:0.85em;margin-top:4px">${total:.0f} total for {trip['passengers']} passengers</div>
    </div>
  </td></tr>

  <!-- Trip details -->
  <tr><td style="padding:16px 28px 0">
    <table width="100%" style="border-collapse:collapse">
      <tr>
        <td style="padding:8px 0;border-bottom:1px solid #1e293b;color:#64748b;font-size:0.83em;width:120px">Route</td>
        <td style="padding:8px 0;border-bottom:1px solid #1e293b;color:#e2e8f0;font-size:0.88em">{trip['origin']} ↔ {trip['destination']} · Nonstop · AA</td>
      </tr>
      <tr>
        <td style="padding:8px 0;border-bottom:1px solid #1e293b;color:#64748b;font-size:0.83em">Dates</td>
        <td style="padding:8px 0;border-bottom:1px solid #1e293b;color:#e2e8f0;font-size:0.88em">{trip['depart_date']} → {trip['return_date']} ({trip['duration_days']} days)</td>
      </tr>
      {"" if not level else f'''<tr>
        <td style="padding:8px 0;border-bottom:1px solid #1e293b;color:#64748b;font-size:0.83em">Google rates</td>
        <td style="padding:8px 0;border-bottom:1px solid #1e293b">
          <span style="color:{level_color};font-weight:700;font-size:0.88em">{level}</span>
          {"&nbsp;· <span style='color:#475569;font-size:0.82em'>Typical " + typical_str + "</span>" if typical_str else ""}
        </td>
      </tr>'''}
    </table>
  </td></tr>

  <!-- Flights -->
  {"" if not flight_rows else f'''
  <tr><td style="padding:16px 28px 0">
    <table width="100%" style="border-collapse:collapse;border-radius:8px;overflow:hidden;font-size:0.87em;border:1px solid #1e293b">
      <tr style="background:#0f172a">
        <td style="padding:6px 10px;color:#475569;font-size:0.78em">Slot</td>
        <td style="padding:6px 10px;color:#475569;font-size:0.78em">Flight</td>
        <td style="padding:6px 10px;color:#475569;font-size:0.78em">Times</td>
        <td style="padding:6px 10px;color:#475569;font-size:0.78em;text-align:right">Price</td>
      </tr>
      {flight_rows}
    </table>
  </td></tr>'''}

  {_kayak_button(aa_url, trip['origin'], trip['destination'])}

  <!-- Reasoning -->
  <tr><td style="padding:20px 28px">
    <div style="background:#0f172a;border-left:3px solid #1e40af;border-radius:0 8px 8px 0;padding:12px 16px">
      <div style="color:#38bdf8;font-size:0.73em;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:5px">Auto's Reasoning</div>
      <div style="color:#94a3b8;font-size:0.86em;line-height:1.5">{signal.get('reasoning', '—')}</div>
    </div>
  </td></tr>
""" + _FOOTER


def send_drop_alert(trip: dict, signal: dict, options: dict, new_ppp: float, drop_pct: float):
    subject = f"🔴 Auto: {trip['label']} dropped {drop_pct:.1f}% → ${new_ppp:.0f}/person — {signal.get('action','?')}"
    html = _drop_alert_html(trip, signal, options, new_ppp, drop_pct)
    _send(subject, html)


# ── Baseline management + alert logic ────────────────────────────────────────

def check_and_alert(trip: dict, signal: dict, options: dict) -> tuple[bool, float]:
    """
    Update baseline and send drop alert if price dropped >= threshold.
    Returns (dropped: bool, drop_pct: float) so tracker can include in status email.
    """
    config    = load_config()
    threshold = config["autopilot"]["price_drop_threshold_pct"]
    trip_id   = trip["id"]

    best_ppp = signal.get("best_price_per_person")
    if best_ppp is None:
        return False, 0.0

    baselines = load_baselines()
    entry     = baselines.get(trip_id, {})
    baseline  = entry.get("baseline_ppp")

    if baseline is None:
        baselines[trip_id] = {
            "baseline_ppp": best_ppp,
            "set_at": datetime.utcnow().isoformat(),
            "alerts_sent": 0,
        }
        save_baselines(baselines)
        print(f"[Reporter] Baseline set for {trip_id}: ${best_ppp:.0f}/pp")
        return False, 0.0

    drop_pct = ((baseline - best_ppp) / baseline) * 100

    if drop_pct >= threshold:
        send_drop_alert(trip, signal, options, best_ppp, drop_pct)
        baselines[trip_id]["baseline_ppp"]  = best_ppp
        baselines[trip_id]["last_alert_at"] = datetime.utcnow().isoformat()
        baselines[trip_id]["alerts_sent"]   = entry.get("alerts_sent", 0) + 1
        save_baselines(baselines)
        print(f"[Reporter] DROP ALERT sent for {trip_id}: ${best_ppp:.0f}/pp (↓{drop_pct:.1f}%)")
        return True, drop_pct
    elif drop_pct > 0:
        print(f"[Reporter] {trip_id}: ${best_ppp:.0f}/pp — down {drop_pct:.1f}% (below {threshold}% threshold)")
    else:
        print(f"[Reporter] {trip_id}: ${best_ppp:.0f}/pp — up {abs(drop_pct):.1f}% from baseline")

    return False, drop_pct
