"""cc-manager status command."""
from __future__ import annotations
import typer
from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.padding import Padding
from rich.rule import Rule

from cc_manager import __version__
from cc_manager.context import get_ctx
from cc_manager.display import console, section, info, dim_info

app = typer.Typer()


@app.command("status")
def status_cmd() -> None:
    """Show cc-manager status."""
    ctx = get_ctx()

    # ── Header banner ────────────────────────────────────────────────────────
    console.print(
        Panel(
            f"[bold bright_cyan]◉ CC-MANAGER[/bold bright_cyan]  [dim]v{__version__}[/dim]"
            f"          [dim]Claude Code Ecosystem Controller[/dim]",
            box=box.DOUBLE_EDGE,
            border_style="cyan",
            padding=(0, 2),
        )
    )
    console.print()

    # ── Installed tools ───────────────────────────────────────────────────────
    installed = ctx.installed.get("tools", {})
    hooks = ctx.settings.get("hooks", {})
    cc_hooks = sum(
        1 for entries in hooks.values()
        for entry in entries
        for h in entry.get("hooks", [])
        if ".cc-manager" in h.get("command", "")
    )

    console.print(Rule("[bold bright_cyan]⚡ INSTALLED TOOLS[/bold bright_cyan]", style="cyan"))
    console.print()

    if installed:
        tbl = Table(
            show_edge=True,
            box=box.SIMPLE_HEAVY,
            border_style="cyan",
            header_style="bold bright_cyan",
            row_styles=["", "dim"],
            padding=(0, 1),
        )
        tbl.add_column("TOOL", style="magenta", min_width=18)
        tbl.add_column("VERSION", style="bright_white", min_width=10)
        tbl.add_column("METHOD", style="cyan", min_width=8)
        tbl.add_column("INSTALLED AT", style="dim", min_width=22)

        for name, tool_info in installed.items():
            tbl.add_row(
                f"[bright_green]✓[/bright_green]  {name}",
                tool_info.get("version", "latest"),
                tool_info.get("method", "—"),
                tool_info.get("installed_at", "—")[:19],
            )
        console.print(Padding(tbl, (0, 2)))
    else:
        console.print(Padding("[dim]  ○  No tools installed yet. Run [bright_cyan]ccm list[/bright_cyan] to browse.[/dim]", (0, 2)))

    console.print()

    # ── Hooks ─────────────────────────────────────────────────────────────────
    console.print(Rule("[bold bright_cyan]⚡ HOOKS[/bold bright_cyan]", style="cyan"))
    console.print()
    if cc_hooks > 0:
        console.print(Padding(f"  [bright_green]✓[/bright_green]  [bright_white]{cc_hooks}[/bright_white] [dim]cc-manager hooks registered in settings.json[/dim]", (0, 2)))
    else:
        console.print(Padding(f"  [bright_red]✗[/bright_red]  [dim]No cc-manager hooks found. Run[/dim] [bright_cyan]ccm init[/bright_cyan] [dim]to register.[/dim]", (0, 2)))
    console.print()

    # ── Last session ──────────────────────────────────────────────────────────
    last = ctx.store.latest("session_end")
    console.print(Rule("[bold bright_cyan]⚡ LAST SESSION[/bold bright_cyan]", style="cyan"))
    console.print()
    if last:
        inp = last.get("input_tokens", 0)
        out = last.get("output_tokens", 0)
        cache = last.get("cache_read", 0)
        cost = last.get("cost_usd", 0.0)
        dur = last.get("duration_min", 0)
        ts = last.get("ts", "")[:19]

        def fmt_tok(n: int) -> str:
            if n >= 1_000_000:
                return f"{n/1_000_000:.1f}M"
            if n >= 1_000:
                return f"{n//1000}K"
            return str(n)

        line = (
            f"  [bright_white]{fmt_tok(inp)}[/bright_white] [dim]input[/dim]  ·  "
            f"[bright_white]{fmt_tok(out)}[/bright_white] [dim]output[/dim]  ·  "
            f"[bright_white]{fmt_tok(cache)}[/bright_white] [dim]cache[/dim]  ·  "
            f"[bright_green]${cost:.4f}[/bright_green]  ·  "
            f"[bright_white]{dur}[/bright_white] [dim]min[/dim]"
        )
        console.print(Padding(line, (0, 2)))
        console.print(Padding(f"  [dim]{ts}[/dim]", (0, 2)))
    else:
        console.print(Padding("[dim]  No session data recorded yet.[/dim]", (0, 2)))

    console.print()
    console.print(Padding("[dim]Run[/dim] [bright_cyan]ccm doctor[/bright_cyan] [dim]for a full diagnostic.[/dim]", (0, 2)))
    console.print()
