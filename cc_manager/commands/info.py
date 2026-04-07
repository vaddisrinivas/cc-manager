"""cc-manager info command."""
from __future__ import annotations
import typer
from rich.console import Console
from cc_manager.context import get_ctx
console = Console()
app = typer.Typer()

@app.command("info")
def info_cmd(name: str = typer.Argument(..., help="Tool name")) -> None:
    """Show detailed info about a tool."""
    ctx = get_ctx()
    tool = next((t for t in ctx.registry if t["name"] == name), None)
    if not tool:
        console.print(f"[red]Tool '{name}' not found.[/red]")
        raise typer.Exit(1)
    console.print(f"[bold]{tool['name']}[/bold] - {tool.get('description','')}")
    console.print(f"Category: {tool.get('category','')}  Tier: {tool.get('tier','')}")
    console.print(f"Repo: {tool.get('repo','N/A')}")
    for m in tool.get("install_methods", []):
        console.print(f"  [{m['type']}] {m.get('command','(manual)')}")
    installed = ctx.installed.get("tools", {}).get(name)
    if installed:
        console.print(f"[green]Installed:[/green] version={installed.get('version')}, method={installed.get('method')}")
