#!/usr/bin/env python3
"""
Auto — Autopilot Flight Tracker
Main entry point. Runs the dashboard API (which includes the scheduler).

Usage:
  python auto.py                    # Start dashboard + tracker
  python auto.py poll               # Run one poll cycle now
  python auto.py status             # Print current tracker status
  python auto.py config             # Print current mission config
"""
import sys
import asyncio
import json
import subprocess
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()
ROOT = Path(__file__).parent


def cmd_status():
    status_file = ROOT / "data" / "tracker_status.json"
    if not status_file.exists():
        console.print("[yellow]No tracker data yet. Run `python auto.py poll` first.[/yellow]")
        return
    status = json.loads(status_file.read_text())
    console.print_json(json.dumps(status, indent=2))


def cmd_config():
    config = json.loads((ROOT / "config.json").read_text())
    table = Table(title="Auto — Active Missions")
    table.add_column("ID", style="dim")
    table.add_column("Label")
    table.add_column("Route")
    table.add_column("Date")
    table.add_column("Pax")
    table.add_column("Max $/pax")
    for m in config["missions"]:
        if m.get("active"):
            table.add_row(
                m["id"],
                m["label"],
                f"{m['origin']} → {m['destination']}",
                m["depart_date"],
                str(m["passengers"]),
                f"${m['max_price_per_person']}",
            )
    console.print(table)


async def cmd_poll():
    sys.path.insert(0, str(ROOT))
    from agents.tracker import poll_cycle
    console.print("[cyan]Auto: Running manual poll cycle...[/cyan]")
    await poll_cycle()
    console.print("[green]Poll complete.[/green]")


def cmd_serve():
    console.print("[cyan]Auto: Starting dashboard API on http://localhost:8000[/cyan]")
    console.print("[dim]Dashboard frontend: open dashboard/frontend in your browser[/dim]")
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "dashboard.backend.main:app",
         "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=ROOT,
    )


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "status":
        cmd_status()
    elif cmd == "config":
        cmd_config()
    elif cmd == "poll":
        asyncio.run(cmd_poll())
    else:
        cmd_serve()
