"""cc-manager list command."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import typer
from rich.rule import Rule

from cc_manager.commands.tui import sparkline as _sparkline_raw
from cc_manager.context import get_ctx
from cc_manager.display import console
from cc_manager.theme import tier_label

app = typer.Typer()

_TIER_ORDER = {"core": 0, "recommended": 1, "useful": 2, "experimental": 3}
_TIER_COLORS = {
    "core":         "bold bright_cyan",
    "recommended":  "bold bright_green",
    "useful":       "bold yellow",
    "experimental": "bold dim",
}
_DIM_DASH_8 = "[dim]────────[/dim]"


def _sparkline(counts: list[int], width: int = 8) -> str:
    """Coloured sparkline; dim dashes when all-zero."""
    if not any(counts):
        return _DIM_DASH_8
    return f"[bright_cyan]{_sparkline_raw(counts, width)}[/bright_cyan]"


def _build_spark_cache(ctx) -> dict[str, str]:
    """One store query → per-tool 7-day sparkline strings."""
    try:
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        events = ctx.store.query(event="tool_use", since=week_ago, limit=10000)
        day_buckets: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for e in events:
            tool_name = e.get("tool", "")
            day = e.get("ts", "")[:10]
            if tool_name and day:
                day_buckets[tool_name][day] += 1
        days = [(datetime.now(timezone.utc) - timedelta(days=6 - i)).strftime("%Y-%m-%d")
                for i in range(7)]
        return {
            name: _sparkline([buckets.get(d, 0) for d in days])
            for name, buckets in day_buckets.items()
        }
    except Exception:
        return {}


def get_tools_list(
    installed_only: bool = False,
    available_only: bool = False,
    category: Optional[str] = None,
    tier: Optional[str] = None,
) -> list[dict]:
    """Return tools list with install status merged in."""
    ctx = get_ctx()
    installed_names = set(ctx.installed.get("tools", {}).keys())
    results = []
    for tool in ctx.registry:
        name = tool["name"]
        is_installed = name in installed_names
        if installed_only and not is_installed:
            continue
        if available_only and is_installed:
            continue
        if category and tool.get("category") != category:
            continue
        if tier and tool.get("tier") != tier:
            continue
        entry = dict(tool)
        entry["installed"] = is_installed
        if is_installed:
            info = ctx.installed["tools"][name]
            entry["installed_version"] = info.get("version", "unknown")
            entry["installed_at"] = info.get("installed_at", "")
        results.append(entry)
    return results


@app.command("list")
def list_cmd(
    installed: bool = typer.Option(False, "--installed", help="Show only installed tools"),
    available: bool = typer.Option(False, "--available", help="Show only not-installed tools"),
    category: Optional[str] = typer.Option(None, "--category", help="Filter by category"),
    tier_filter: Optional[str] = typer.Option(None, "--tier", help="Filter by tier"),
) -> None:
    """List tools in the registry, grouped by tier with 7-day sparklines."""
    tools = get_tools_list(
        installed_only=installed,
        available_only=available,
        category=category,
        tier=tier_filter,
    )

    ctx = get_ctx()
    spark_cache = _build_spark_cache(ctx)  # one store read covers all installed tools
    console.print()

    groups: dict[str, list[dict]] = defaultdict(list)
    for t in tools:
        groups[t.get("tier", "useful")].append(t)

    for tier_key in sorted(groups.keys(), key=lambda x: _TIER_ORDER.get(x, 99)):
        tier_tools = groups[tier_key]
        color = _TIER_COLORS.get(tier_key, "dim")
        console.print(Rule(
            f"[{color}]◆ {tier_key.upper()}[/{color}]  [dim]({len(tier_tools)})[/dim]",
            style="dim",
        ))
        console.print()
        for tool in tier_tools:
            name = tool["name"]
            is_inst = tool.get("installed", False)
            mark = "[bright_green]✓[/bright_green]" if is_inst else "[dim]○[/dim]"
            name_styled = f"[bright_white]{name}[/bright_white]" if is_inst else f"[dim]{name}[/dim]"
            cat = f"[dim]{tool.get('category', '')}[/dim]"
            spark = spark_cache.get(name, _DIM_DASH_8) if is_inst else _DIM_DASH_8
            hint = ""
            if not is_inst:
                methods = tool.get("install_methods", [])
                if methods:
                    cmd = methods[0].get("command", "")
                    if cmd:
                        hint = f"  [dim]→ {cmd[:42]}[/dim]"
            console.print(f"  {mark} {name_styled:<32} {cat:<24} {spark}{hint}")
        console.print()

    installed_count = sum(1 for t in tools if t.get("installed"))
    console.print(f"  [dim]{len(tools)} tools · {installed_count} installed[/dim]")
    console.print()
