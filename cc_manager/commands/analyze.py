"""cc-manager analyze command."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import typer
from rich import box
from rich.panel import Panel
from rich.padding import Padding
from rich.progress import Progress, BarColumn, TextColumn, TaskProgressColumn
from rich.rule import Rule
from rich.table import Table

from cc_manager.context import get_ctx, parse_duration
from cc_manager.display import console
from cc_manager.context import fmt_tokens

app = typer.Typer()


def compute_stats(period_days: int = 7, session_id: Optional[str] = None) -> dict:
    """Compute usage stats from the event store."""
    ctx = get_ctx()

    since = datetime.now(timezone.utc) - timedelta(days=period_days)

    if session_id:
        session_events = ctx.store.query(session=session_id)
        sessions = [e for e in session_events if e.get("event") == "session_end"]
        all_events = session_events
    else:
        sessions = ctx.store.sessions(since=since)
        all_events = ctx.store.query(since=since, limit=100000)

    if not sessions:
        return {
            "sessions": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cache_read": 0,
            "total_cost_usd": 0.0,
            "avg_duration_min": 0.0,
            "sessions_per_day": 0.0,
            "avg_tokens_per_session": 0.0,
            "compaction_count": 0,
            "model_breakdown": {},
            "top_bash_commands": [],
        }

    total_input = sum(s.get("input_tokens", 0) for s in sessions)
    total_output = sum(s.get("output_tokens", 0) for s in sessions)
    total_cache_read = sum(s.get("cache_read", 0) for s in sessions)
    total_cost = sum(s.get("cost_usd", 0.0) for s in sessions)

    durations = [s.get("duration_min", 0) for s in sessions]
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    model_counter: Counter = Counter()
    for s in sessions:
        model = s.get("model", "unknown")
        model_counter[model] += 1

    # Compaction count
    compact_events = [e for e in all_events if e.get("event") == "compact"]
    compaction_count = len(compact_events)

    # Top bash commands
    tool_use_events = [e for e in all_events if e.get("event") == "tool_use" and e.get("tool") == "Bash"]
    bash_cmds: Counter = Counter()
    for e in tool_use_events:
        cmd = e.get("command", "").split()[0] if e.get("command") else ""
        if cmd:
            bash_cmds[cmd] += 1

    return {
        "sessions": len(sessions),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cache_read": total_cache_read,
        "total_cost_usd": round(total_cost, 4),
        "avg_duration_min": round(avg_duration, 1),
        "sessions_per_day": round(len(sessions) / max(period_days, 1), 2),
        "avg_tokens_per_session": round((total_input + total_output) / max(len(sessions), 1)),
        "compaction_count": compaction_count,
        "model_breakdown": dict(model_counter),
        "top_bash_commands": bash_cmds.most_common(10),
    }


@app.command("analyze")
def analyze_cmd(
    period: str = typer.Option("7d", "--period", help="Analysis period (e.g., 7d, 30d)"),
    session: Optional[str] = typer.Option(None, "--session", help="Analyze specific session UUID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Analyze Claude Code usage stats."""
    try:
        td = parse_duration(period)
        period_days = int(td.total_seconds() / 86400)
    except ValueError:
        period_days = 7

    stats = compute_stats(period_days=period_days, session_id=session)

    if output_json:
        console.print(json.dumps(stats, indent=2))
        return

    console.print()

    # ── Summary banner ────────────────────────────────────────────────────────
    period_label = f"Last {period_days}d" if not session else f"Session {session[:8]}"
    console.print(
        Panel(
            f"[bold bright_cyan]USAGE ANALYSIS[/bold bright_cyan]  [dim]·[/dim]  [bright_white]{period_label}[/bright_white]",
            box=box.DOUBLE_EDGE,
            border_style="cyan",
            padding=(0, 2),
        )
    )
    console.print()

    # ── Key metrics grid ──────────────────────────────────────────────────────
    s = stats
    total_tok = s["total_input_tokens"] + s["total_output_tokens"]
    metrics = [
        ("Total Cost", f"[bright_green]${s['total_cost_usd']:.4f}[/bright_green]"),
        ("Total Tokens", f"[bright_white]{fmt_tokens(total_tok)}[/bright_white]"),
        ("Sessions", f"[bright_white]{s['sessions']}[/bright_white]  [dim]{s['sessions_per_day']}/day avg[/dim]"),
        ("Avg Duration", f"[bright_white]{s['avg_duration_min']}[/bright_white] [dim]min[/dim]"),
        ("Input Tokens", f"[bright_white]{fmt_tokens(s['total_input_tokens'])}[/bright_white]"),
        ("Output Tokens", f"[bright_white]{fmt_tokens(s['total_output_tokens'])}[/bright_white]"),
        ("Cache Read", f"[bright_white]{fmt_tokens(s['total_cache_read'])}[/bright_white]"),
        ("Compactions", f"[bright_white]{s['compaction_count']}[/bright_white]"),
    ]

    tbl = Table(
        show_edge=False,
        box=None,
        padding=(0, 2),
        show_header=False,
    )
    tbl.add_column("metric", style="dim", min_width=18)
    tbl.add_column("value", min_width=28)
    tbl.add_column("metric2", style="dim", min_width=18)
    tbl.add_column("value2", min_width=28)

    pairs = list(zip(metrics[::2], metrics[1::2]))
    for (k1, v1), (k2, v2) in pairs:
        tbl.add_row(k1, v1, k2, v2)

    console.print(Padding(tbl, (0, 2)))
    console.print()

    # ── Daily breakdown table ─────────────────────────────────────────────────
    if s["sessions"] > 0:
        console.print(Rule("[bold bright_cyan]⚡ DAILY BREAKDOWN[/bold bright_cyan]", style="cyan"))
        console.print()

        breakdown_tbl = Table(
            show_edge=True,
            box=box.SIMPLE_HEAVY,
            border_style="cyan",
            header_style="bold bright_cyan",
            row_styles=["", "dim"],
            padding=(0, 1),
        )
        breakdown_tbl.add_column("METRIC", style="dim", min_width=24)
        breakdown_tbl.add_column("VALUE", style="bright_white", min_width=18)
        breakdown_tbl.add_row("Sessions", str(s["sessions"]))
        breakdown_tbl.add_row("Input Tokens", f"{s['total_input_tokens']:,}")
        breakdown_tbl.add_row("Output Tokens", f"{s['total_output_tokens']:,}")
        breakdown_tbl.add_row("Cache Read Tokens", f"{s['total_cache_read']:,}")
        breakdown_tbl.add_row("Estimated Cost", f"${s['total_cost_usd']:.4f}")
        breakdown_tbl.add_row("Avg Duration (min)", str(s["avg_duration_min"]))
        breakdown_tbl.add_row("Sessions/Day", str(s["sessions_per_day"]))
        breakdown_tbl.add_row("Compactions", str(s["compaction_count"]))

        console.print(Padding(breakdown_tbl, (0, 2)))
        console.print()

    # ── Model breakdown bar chart ─────────────────────────────────────────────
    if s["model_breakdown"]:
        console.print(Rule("[bold bright_cyan]⚡ MODEL BREAKDOWN[/bold bright_cyan]", style="cyan"))
        console.print()

        total_sess = sum(s["model_breakdown"].values())
        with Progress(
            TextColumn("  [dim]{task.description:<12}[/dim]", justify="left"),
            BarColumn(bar_width=24, style="cyan", complete_style="bright_cyan"),
            TextColumn(" [bright_white]{task.percentage:>4.0f}%[/bright_white]"),
            TextColumn("  [dim]{task.fields[cost]}[/dim]"),
            console=console,
            expand=False,
        ) as prog:
            for model, count in sorted(s["model_breakdown"].items(), key=lambda x: -x[1]):
                pct = count / total_sess if total_sess > 0 else 0
                # Approximate cost per model (split proportionally from total)
                model_cost = s["total_cost_usd"] * pct
                task = prog.add_task(
                    model,
                    total=total_sess,
                    completed=count,
                    cost=f"${model_cost:.2f}",
                )
        console.print()

    # ── Top commands ─────────────────────────────────────────────────────────
    if s["top_bash_commands"]:
        console.print(Rule("[bold bright_cyan]⚡ TOP BASH COMMANDS[/bold bright_cyan]", style="cyan"))
        console.print()

        cmd_tbl = Table(
            show_edge=True,
            box=box.SIMPLE_HEAVY,
            border_style="cyan",
            header_style="bold bright_cyan",
            row_styles=["", "dim"],
            padding=(0, 1),
        )
        cmd_tbl.add_column("COMMAND", style="magenta", min_width=20)
        cmd_tbl.add_column("USES", style="bright_white", min_width=8)

        for cmd, count in s["top_bash_commands"]:
            cmd_tbl.add_row(cmd, str(count))

        console.print(Padding(cmd_tbl, (0, 2)))
        console.print()
