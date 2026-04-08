"""cc-manager search command."""
from __future__ import annotations
import difflib
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


def _highlight(text: str, query: str) -> str:
    """Wrap occurrences of query in text with bright_yellow markup."""
    q = query.lower()
    if not q or q not in text.lower():
        return text
    result = []
    lower = text.lower()
    i = 0
    while i < len(text):
        pos = lower.find(q, i)
        if pos == -1:
            result.append(text[i:])
            break
        result.append(text[i:pos])
        result.append(f"[bright_yellow]{text[pos:pos + len(q)]}[/bright_yellow]")
        i = pos + len(q)
    return "".join(result)


def _fuzzy_score(tool: dict, q: str) -> float:
    """Return a fuzzy match score (0-1) for a tool against query.

    Ordered cheapest-first: exact → token → difflib (only when needed).
    """
    name = tool["name"].lower()
    desc = tool.get("description", "").lower()
    cat = tool.get("category", "").lower()

    if q in name:
        return 1.0 + (1.0 - len(q) / max(len(name), 1))
    if q in desc or q in cat:
        return 0.8

    # Token overlap (set intersection — O(words), cheaper than difflib)
    q_words = set(q.split())
    target_words = set((name + " " + desc + " " + cat).split())
    overlap = q_words & target_words
    if overlap:
        return 0.4 + 0.1 * len(overlap)

    # difflib only as last resort
    ratio = difflib.SequenceMatcher(None, q, name).ratio()
    return ratio if ratio >= 0.5 else 0.0


@app.command("search")
def search_cmd(query: str = typer.Argument(..., help="Search query")) -> None:
    """Search tools by name, description, or category. Supports fuzzy matching."""
    ctx = get_ctx()
    q = query.lower().strip()

    # Score every tool and keep those with score > 0
    scored = [(t, _fuzzy_score(t, q)) for t in ctx.registry]
    results = sorted(
        [(t, s) for t, s in scored if s > 0],
        key=lambda x: x[1],
        reverse=True,
    )

    console.print()

    if not results:
        console.print(
            Panel(
                f"  [bright_red]No tools matched:[/bright_red] [bright_white]{query}[/bright_white]\n\n"
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

    for tool, score in results:
        tier = tool.get("tier", "")
        category = tool.get("category", "—")
        desc = _highlight(tool.get("description", ""), query)
        name = _highlight(tool["name"], query)
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
                    title=f"[bold bright_cyan]◆ {name}[/bold bright_cyan]",
                    border_style="cyan",
                    box=box.SIMPLE_HEAVY,
                    padding=(0, 1),
                ),
                (0, 1),
            )
        )

    console.print()
