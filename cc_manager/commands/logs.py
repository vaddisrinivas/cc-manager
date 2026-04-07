"""cc-manager logs command."""
from __future__ import annotations
import time
from typing import Optional
import typer
from rich.rule import Rule
from rich.text import Text
from rich.columns import Columns

from cc_manager.context import get_ctx, parse_duration
from cc_manager.display import console

app = typer.Typer()

# Color mapping for event types
_EVENT_COLORS = {
    "session_end": "bright_cyan",
    "session_start": "bright_green",
    "install": "magenta",
    "uninstall": "yellow",
    "doctor": "dim",
    "compact": "cyan",
    "init": "bright_cyan",
    "backup": "dim",
    "tool_use": "dim",
    "error": "bright_red",
}


def _event_color(event: str) -> str:
    return _EVENT_COLORS.get(event.lower(), "white")


def _format_record(r: dict) -> str:
    """Format a single event record as a styled log line."""
    ts = r.get("ts", "")[:19].replace("T", "  ")
    event = r.get("event", "unknown").upper()
    color = _event_color(r.get("event", ""))

    # Build detail string based on event type
    details = []
    ev = r.get("event", "").lower()
    if ev == "session_end":
        inp = r.get("input_tokens", 0)
        out = r.get("output_tokens", 0)
        cost = r.get("cost_usd", 0.0)
        dur = r.get("duration_min", 0)
        def ftok(n):
            return f"{n//1000}K" if n >= 1000 else str(n)
        details.append(f"{ftok(inp)} in · {ftok(out)} out · ${cost:.4f} · {dur}min")
    elif ev == "session_start":
        cwd = r.get("cwd", "")
        if cwd:
            details.append(cwd)
    elif ev == "install":
        tool = r.get("tool", "")
        version = r.get("version", "")
        method = r.get("method", "")
        if tool:
            details.append(f"{tool} {version} via {method}".strip())
    elif ev == "doctor":
        res = r.get("results", {})
        if res:
            n_ok = sum(1 for v in res.values() if v == "ok")
            n_warn = sum(1 for v in res.values() if v == "warn")
            n_fail = sum(1 for v in res.values() if v == "fail")
            details.append(f"{n_ok} ok · {n_warn} warn · {n_fail} fail")
    elif ev == "compact":
        trigger = r.get("trigger", "")
        if trigger:
            details.append(f"trigger={trigger}")
    else:
        # Generic: show any extra fields
        skip = {"ts", "event", "session"}
        extras = {k: v for k, v in r.items() if k not in skip}
        if extras:
            details.append("  ".join(f"{k}={v}" for k, v in list(extras.items())[:3]))

    detail_str = "  ".join(details)

    ts_part = f"[dim]{ts}[/dim]"
    event_part = f"[{color}]{event:<16}[/{color}]"
    detail_part = f"[dim]{detail_str}[/dim]" if detail_str else ""

    return f"  {ts_part}  {event_part}  {detail_part}"


@app.command("logs")
def logs_cmd(
    event: Optional[str] = typer.Option(None, "--event"),
    tool: Optional[str] = typer.Option(None, "--tool"),
    since: Optional[str] = typer.Option(None, "--since"),
    follow: bool = typer.Option(False, "--follow", "-f"),
    n: int = typer.Option(20, "--lines", "-n"),
) -> None:
    """Show recent events from the store."""
    from datetime import datetime, timezone
    ctx = get_ctx()
    since_dt = None
    if since:
        try:
            td = parse_duration(since)
            since_dt = datetime.now(timezone.utc) - td
        except ValueError:
            pass

    console.print()
    console.print(Rule(f"[bold bright_cyan]◉ EVENT LOG[/bold bright_cyan]  [dim]last {n}[/dim]", style="cyan"))
    console.print()

    if follow:
        pos = ctx.store.path.stat().st_size if ctx.store.path.exists() else 0
        import json
        while True:
            if ctx.store.path.exists():
                with open(ctx.store.path) as f:
                    f.seek(pos)
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                r = json.loads(line)
                                console.print(_format_record(r))
                            except Exception:
                                console.print(f"  [dim]{line}[/dim]")
                    pos = f.tell()
            time.sleep(1)
    else:
        records = ctx.store.query(event=event, tool=tool, since=since_dt, limit=n)
        if not records:
            console.print("  [dim]No events found.[/dim]")
        else:
            for r in records:
                console.print(_format_record(r))

    console.print()
