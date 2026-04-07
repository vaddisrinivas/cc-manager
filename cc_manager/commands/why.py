"""cc-manager why command."""
from __future__ import annotations
import typer
from rich.console import Console
from cc_manager.context import get_ctx
console = Console()
app = typer.Typer()

@app.command("why")
def why_cmd(name: str = typer.Argument(...)) -> None:
    """Explain why a tool is installed."""
    ctx = get_ctx()
    if name not in ctx.installed.get("tools", {}):
        console.print(f"[yellow]{name} is not installed.[/yellow]"); return
    event = ctx.store.latest("install")
    # Find the specific install event for this tool
    all_install = ctx.store.query(event="install", tool=name)
    if all_install:
        e = all_install[0]
        console.print(f"Added by `ccm install {name}` on {e.get('ts','unknown')}")
    else:
        info = ctx.installed["tools"][name]
        console.print(f"Installed on {info.get('installed_at','unknown')} via {info.get('method','unknown')}")
