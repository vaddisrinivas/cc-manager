"""cc-manager search command."""
from __future__ import annotations
import typer
from rich import box
from rich.panel import Panel
from rich.padding import Padding

from cc_manager.context import get_ctx
from cc_manager.display import console
from cc_manager.theme import tier_label

app = typer.Typer()


def _install_hint(tool: dict) -> str:
    methods = tool.get("install_methods", [])
    if methods:
        return methods[0].get("command", "—")
    return "—"


@app.command("search")
def search_cmd(query: str = typer.Argument(..., help="Search query")) -> None:
    """Search tools by name, description, or category."""
    ctx = get_ctx()
    q = query.lower()
    results = [
        t for t in ctx.registry
        if q in t["name"].lower() or q in t.get("description", "").lower() or q in t.get("category", "").lower()
    ]

    console.print()

    if not results:
        console.print(
            Panel(
                f"  [bright_red]No tools matched query:[/bright_red] [bright_white]{query}[/bright_white]\n\n"
                f"  [dim]Run [bright_cyan]ccm list[/bright_cyan] to browse all available tools.[/dim]",
                title="[bold bright_red]✗ NO RESULTS FOUND[/bold bright_red]",
                border_style="bright_red",
                box=box.HEAVY,
                padding=(0, 1),
            )
        )
        console.print()
        return

    console.print(
        f"  [dim]Found[/dim] [bright_white]{len(results)}[/bright_white] [dim]result{'s' if len(results) != 1 else ''} for[/dim] [bright_cyan]\"{query}\"[/bright_cyan]\n"
    )

    for tool in results[:5]:
        tier = tool.get("tier", "")
        category = tool.get("category", "—")
        desc = tool.get("description", "")
        hint = _install_hint(tool)

        body = (
            f"  [dim]{desc}[/dim]\n"
            f"  {tier_label(tier)}  [dim]·[/dim]  [magenta]{category}[/magenta]"
            + (f"  [dim]·[/dim]  [dim]{hint}[/dim]" if hint != "—" else "")
        )

        console.print(
            Padding(
                Panel(
                    body,
                    title=f"[bold bright_cyan]◆ {tool['name']}[/bold bright_cyan]",
                    border_style="cyan",
                    box=box.SIMPLE_HEAVY,
                    padding=(0, 1),
                ),
                (0, 1),
            )
        )

    if len(results) > 5:
        console.print(f"  [dim]... and {len(results) - 5} more. Refine your query for fewer results.[/dim]")

    console.print()
