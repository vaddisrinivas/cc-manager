"""cc-manager recommend command."""
from __future__ import annotations
import typer
from rich import box
from rich.panel import Panel
from rich.padding import Padding

from cc_manager.context import get_ctx
from cc_manager.commands.analyze import compute_stats
from cc_manager.display import console

app = typer.Typer()


@app.command("recommend")
def recommend_cmd() -> None:
    """Recommend tools based on usage patterns."""
    ctx = get_ctx()
    stats = compute_stats(period_days=7)
    installed = set(ctx.installed.get("tools", {}).keys())
    recommendations = []

    if "rtk" not in installed:
        avg_tokens = stats.get("avg_tokens_per_session", 0)
        if avg_tokens > 500_000:
            recommendations.append(("rtk", f"avg session tokens={avg_tokens:,} > 500K"))

    if stats.get("compaction_count", 0) > 2 * max(stats.get("sessions", 1), 1):
        if "rtk" not in installed:
            recommendations.append(("rtk", "high compaction frequency"))

    mcp_servers = ctx.settings.get("mcpServers", {})
    if not mcp_servers:
        if "context7" not in installed:
            recommendations.append(("context7", "no MCP servers configured"))
        if "playwright-mcp" not in installed:
            recommendations.append(("playwright-mcp", "no browser automation MCP"))

    security_tools = [t for t in installed if "security" in (
        next((x.get("category","") for x in ctx.registry if x["name"]==t), "")
    )]
    if not security_tools and "trail-of-bits" not in installed:
        recommendations.append(("trail-of-bits", "no security tool installed"))

    opus_count = stats.get("model_breakdown", {}).get("opus", 0)
    total_sessions = stats.get("sessions", 0)
    if total_sessions > 0 and opus_count / total_sessions > 0.5:
        recommendations.append((None, "Opus >50% of sessions — consider sonnet for cost savings"))

    if "claude-squad" not in installed:
        recommendations.append(("claude-squad", "no multi-agent orchestration"))

    console.print()

    if not recommendations:
        console.print(
            Panel(
                "  [bright_green]✦[/bright_green]  [bright_white]Your setup looks great![/bright_white]\n\n"
                "  [dim]No recommendations at this time.[/dim]",
                title="[bold bright_green]◉ ALL CLEAR[/bold bright_green]",
                border_style="bright_green",
                box=box.DOUBLE_EDGE,
                padding=(0, 1),
            )
        )
        console.print()
        return

    for tool, reason in recommendations:
        if tool:
            body = (
                f"  [dim]{reason}.[/dim]\n\n"
                f"  [bright_cyan]▶ ccm install {tool}[/bright_cyan]"
            )
        else:
            body = f"  [yellow]{reason}[/yellow]"

        console.print(
            Padding(
                Panel(
                    body,
                    title="[bold bright_cyan]⚡ RECOMMENDATION[/bold bright_cyan]",
                    border_style="cyan",
                    box=box.SIMPLE_HEAVY,
                    padding=(0, 2),
                ),
                (0, 1),
            )
        )

    console.print()
