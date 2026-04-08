"""cc-manager recommend command."""
from __future__ import annotations
from typing import Any

import typer
from rich import box
from rich.panel import Panel
from rich.padding import Padding

from cc_manager.context import get_ctx
from cc_manager.display import console

app = typer.Typer()


def get_recommendations(ctx: Any) -> list[dict]:
    """Return data-driven recommendations from compute_stats. Empty if no sessions."""
    from cc_manager.commands.analyze import compute_stats

    stats = compute_stats(period_days=7)
    if stats.get("sessions", 0) == 0:
        return []

    installed = set(ctx.installed.get("tools", {}).keys())
    recs: list[dict] = []

    avg_tokens = stats.get("avg_tokens_per_session", 0)
    compaction_count = stats.get("compaction_count", 0)
    total_sessions = stats.get("sessions", 0)
    model_breakdown = stats.get("model_breakdown", {})
    total_cost = stats.get("total_cost_usd", 0.0)
    total_output = stats.get("total_output_tokens", 0)
    avg_output = total_output // max(total_sessions, 1)

    if "rtk" not in installed and avg_tokens > 500_000:
        recs.append({"tool": "rtk", "message": f"avg {avg_tokens // 1000}K tokens/session — token filter saves 60-90%", "install_cmd": "ccm install rtk"})
    if "rtk" not in installed and compaction_count > total_sessions:
        recs.append({"tool": "rtk", "message": f"{compaction_count} compactions in {total_sessions} sessions — context pressure is high", "install_cmd": "ccm install rtk"})

    opus_sessions = sum(v for k, v in model_breakdown.items() if "opus" in k.lower())
    if total_sessions > 3 and opus_sessions / total_sessions > 0.5:
        recs.append({"tool": None, "message": f"Opus used in {opus_sessions}/{total_sessions} sessions — sonnet cuts cost ~5x", "install_cmd": None})

    if "cc-sentinel" not in installed and total_cost > 1.0:
        recs.append({"tool": "cc-sentinel", "message": f"${total_cost:.2f} spent this week — sentinel intercepts waste in real-time", "install_cmd": "ccm install cc-sentinel"})
    if "context7" not in installed and not ctx.settings.get("mcpServers", {}):
        recs.append({"tool": "context7", "message": "No MCP servers — context7 injects version-accurate docs into context", "install_cmd": "ccm install context7"})
    if "caveman" not in installed and avg_output > 200_000:
        recs.append({"tool": "caveman", "message": f"avg {avg_output // 1000}K output tokens/session — caveman skill cuts output ~75%", "install_cmd": "ccm install caveman"})
    if "cc-retrospect" not in installed and total_sessions >= 5:
        recs.append({"tool": "cc-retrospect", "message": f"{total_sessions} sessions recorded — retrospect surfaces waste patterns and habit insights", "install_cmd": "ccm install cc-retrospect"})
    if "cc-budget" not in installed and total_cost > 2.0:
        recs.append({"tool": "cc-budget", "message": f"${total_cost:.2f} this week — cc-budget sets per-prompt limits and pacing targets", "install_cmd": "ccm install cc-budget"})

    return recs


@app.command("recommend")
def recommend_cmd() -> None:
    """Recommend tools based on usage patterns."""
    ctx = get_ctx()
    recs = get_recommendations(ctx)
    console.print()
    if not recs:
        console.print(Panel(
            "  [bright_green]✦[/bright_green]  [bright_white]Your setup looks great![/bright_white]\n\n  [dim]No recommendations at this time.[/dim]",
            title="[bold bright_green]◉ ALL CLEAR[/bold bright_green]",
            border_style="bright_green", box=box.DOUBLE_EDGE, padding=(0, 1),
        ))
        console.print()
        return
    for rec in recs:
        tool, reason, install_cmd = rec.get("tool"), rec.get("message", ""), rec.get("install_cmd")
        body = f"  [dim]{reason}.[/dim]\n\n  [bright_cyan]▶ {install_cmd}[/bright_cyan]" if install_cmd else f"  [yellow]{reason}[/yellow]"
        console.print(Padding(Panel(body, title="[bold bright_cyan]⚡ RECOMMENDATION[/bold bright_cyan]",
                                    border_style="cyan", box=box.SIMPLE_HEAVY, padding=(0, 2)), (0, 1)))
    console.print()
