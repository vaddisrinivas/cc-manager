"""cc-manager pin command."""
from __future__ import annotations
import json
import typer
from rich.console import Console
import cc_manager.context as ctx_mod
from cc_manager.context import get_ctx
console = Console()
app = typer.Typer()

def _save(ctx):
    ctx_mod.REGISTRY_PATH.write_text(json.dumps(ctx.installed, indent=2), encoding="utf-8")

@app.command("pin")
def pin_cmd(name: str = typer.Argument(...)) -> None:
    """Pin a tool version."""
    ctx = get_ctx()
    if name not in ctx.installed.get("tools", {}):
        console.print(f"[red]{name} not installed.[/red]"); raise typer.Exit(1)
    ctx.installed["tools"][name]["pinned"] = True
    _save(ctx); console.print(f"[green]Pinned[/green] {name}")

@app.command("unpin")
def unpin_cmd(name: str = typer.Argument(...)) -> None:
    """Unpin a tool."""
    ctx = get_ctx()
    if name not in ctx.installed.get("tools", {}):
        console.print(f"[red]{name} not installed.[/red]"); raise typer.Exit(1)
    ctx.installed["tools"][name]["pinned"] = False
    _save(ctx); console.print(f"[green]Unpinned[/green] {name}")

@app.command("pin-list")
def pin_list_cmd() -> None:
    """Show pinned tools."""
    ctx = get_ctx()
    pinned = [n for n,i in ctx.installed.get("tools",{}).items() if i.get("pinned")]
    if pinned:
        for n in pinned: console.print(f"  {n}")
    else:
        console.print("No pinned tools.")
