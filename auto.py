#!/usr/bin/env python3
"""
Auto — Autopilot Flight Tracker

Usage:
  python auto.py poll          # Run one poll cycle and push to GitHub
  python auto.py debug         # Dump raw SerpAPI response (no push) — use to diagnose missing flights
  python auto.py status        # Print tracker status
"""
import sys
import asyncio
import json
from pathlib import Path
from rich.console import Console

console = Console()
ROOT = Path(__file__).parent


def cmd_status():
    status_file = ROOT / "data" / "tracker_status.json"
    if not status_file.exists():
        console.print("[yellow]No tracker data yet. Run `python auto.py poll` first.[/yellow]")
        return
    console.print_json(json.dumps(json.loads(status_file.read_text()), indent=2))


async def cmd_poll():
    sys.path.insert(0, str(ROOT))
    from agents.tracker import poll_cycle
    console.print("[cyan]Auto: Running poll cycle...[/cyan]")
    await poll_cycle()
    console.print("[green]Poll complete.[/green]")


async def cmd_debug():
    """
    Dump the raw SerpAPI response for every active trip.
    Use this to diagnose why flights aren't being picked up.
    Prints every flight, whether it passed or failed each filter, and why.
    Does NOT write any files or push to GitHub.
    """
    sys.path.insert(0, str(ROOT))
    from agents.scraper import run_all_trips
    console.print("[cyan]Auto DEBUG: fetching raw SerpAPI data (no push)...[/cyan]\n")
    results = await run_all_trips(debug=True)
    for trip_id, result in results.items():
        if result.get("error"):
            console.print(f"[red]ERROR {trip_id}: {result['error']}[/red]")
        else:
            opts = result["options"]
            console.print(f"[green]{trip_id}[/green]")
            console.print(f"  Morning flights:   {len(opts.get('morning', []))}")
            console.print(f"  Afternoon flights: {len(opts.get('afternoon', []))}")
            console.print(f"  AA nonstop count:  {opts.get('aa_nonstop_count', 0)}")
            pi = opts.get("price_insights", {})
            console.print(f"  Google price level: {pi.get('price_level', 'N/A')}")
            console.print(f"  Typical range/pp:  {pi.get('typical_range_ppp', 'N/A')}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "poll"
    if cmd == "status":
        cmd_status()
    elif cmd == "debug":
        asyncio.run(cmd_debug())
    elif cmd == "poll":
        asyncio.run(cmd_poll())
    else:
        console.print(f"[red]Unknown command: {cmd}[/red]")
        console.print("Usage: python auto.py [poll|debug|status]")
        sys.exit(1)
