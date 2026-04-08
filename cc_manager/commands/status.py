"""cc-manager status command — compact single-screen overview."""
from __future__ import annotations
import typer
from rich import box
from rich.panel import Panel
from rich.rule import Rule

from cc_manager import __version__
from cc_manager.context import get_ctx, fmt_tokens, get_week_stats
from cc_manager.display import console
from cc_manager.theme import health_dot

app = typer.Typer()


@app.command("status")
def status_cmd() -> None:
    """Compact single-screen status: tools, session, health, next action."""
    ctx = get_ctx()
    installed = ctx.installed.get("tools", {})
    hooks = ctx.settings.get("hooks", {})

    cc_hooks = sum(
        1 for entries in hooks.values()
        for entry in entries
        for h in entry.get("hooks", [])
        if ".cc-manager" in h.get("command", "")
    )

    # Single store read covers both week stats and last session
    recent, week_cost, week_sessions, week_tokens = get_week_stats(ctx.store)
    last = recent[-1] if recent else None

    # ── Health signals ───────────────────────────────────────────────────────
    hooks_ok = cc_hooks >= 2
    store_ok = ctx.store.path.parent.exists()

    # ── Banner ───────────────────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        f"[bold bright_cyan]◉ CC-MANAGER[/bold bright_cyan]  [dim]v{__version__}[/dim]   "
        f"[dim]tools:[/dim] [bright_white]{len(installed)}[/bright_white]   "
        f"[dim]week:[/dim] [bright_green]${week_cost:.2f}[/bright_green]  "
        f"[dim]{week_sessions}s  {fmt_tokens(week_tokens)}tok[/dim]",
        box=box.DOUBLE_EDGE, border_style="cyan", padding=(0, 2),
    ))

    # ── Tools ────────────────────────────────────────────────────────────────
    console.print(Rule("[bold bright_cyan]⚡ TOOLS[/bold bright_cyan]", style="cyan"))
    console.print()
    if installed:
        cols: list[str] = []
        for name, info in installed.items():
            method = info.get("method", "—")
            pinned = " [dim]📌[/dim]" if info.get("pinned") else ""
            cols.append(f"  [bright_green]✓[/bright_green] [bright_white]{name}[/bright_white] [dim]{method}[/dim]{pinned}")
        # Print in 2-column layout if many tools
        if len(cols) > 4:
            mid = (len(cols) + 1) // 2
            left, right = cols[:mid], cols[mid:]
            for l, r in zip(left, right + [""]):
                console.print(f"{l:<52}{r}")
        else:
            for c in cols:
                console.print(c)
    else:
        console.print("  [dim]○  No tools installed. Run [bright_cyan]ccm list[/bright_cyan] → [bright_cyan]ccm install <name>[/bright_cyan][/dim]")
    console.print()

    # ── Last session ─────────────────────────────────────────────────────────
    console.print(Rule("[bold bright_cyan]⚡ LAST SESSION[/bold bright_cyan]", style="cyan"))
    console.print()
    if last:
        inp   = last.get("input_tokens", 0)
        out   = last.get("output_tokens", 0)
        cache = last.get("cache_read", 0)
        cost  = last.get("cost_usd", 0.0)
        dur   = last.get("duration_min", 0)
        ts    = last.get("ts", "")[:19].replace("T", " ")
        console.print(
            f"  [dim]{ts}[/dim]  "
            f"[bright_white]{fmt_tokens(inp)}[/bright_white][dim]in[/dim]  "
            f"[bright_white]{fmt_tokens(out)}[/bright_white][dim]out[/dim]  "
            f"[bright_white]{fmt_tokens(cache)}[/bright_white][dim]cache[/dim]  "
            f"[bright_green]${cost:.4f}[/bright_green]  "
            f"[dim]{dur}min[/dim]"
        )
    else:
        console.print("  [dim]No session data yet — start a Claude Code session to populate.[/dim]")
    console.print()

    # ── Health ───────────────────────────────────────────────────────────────
    console.print(Rule("[bold bright_cyan]⚡ HEALTH[/bold bright_cyan]", style="cyan"))
    console.print()
    health_rows = [
        (health_dot(hooks_ok),        "hooks",  f"{cc_hooks} cc-manager hooks registered" if hooks_ok else "no hooks — run [bright_cyan]ccm init[/bright_cyan]"),
        (health_dot(store_ok),         "store",  str(ctx.store.path.parent) if store_ok else "store dir missing"),
        (health_dot(len(installed)>0, len(installed)==0), "tools", f"{len(installed)} installed" if installed else "none installed"),
    ]
    for icon, label, msg in health_rows:
        console.print(f"  {icon}  [dim]{label:<10}[/dim] {msg}")
    console.print()

    # ── Next action ──────────────────────────────────────────────────────────
    if not hooks_ok:
        next_action = "[bright_cyan]ccm init[/bright_cyan]  [dim]→ register hooks[/dim]"
    elif not installed:
        next_action = "[bright_cyan]ccm list[/bright_cyan]  [dim]→ browse available tools[/dim]"
    elif week_sessions > 5:
        next_action = "[bright_cyan]ccm recommend[/bright_cyan]  [dim]→ see personalized suggestions[/dim]"
    else:
        next_action = "[bright_cyan]ccm doctor[/bright_cyan]  [dim]→ full diagnostic[/dim]"

    console.print(f"  [dim]▶ next:[/dim]  {next_action}")
    console.print()
