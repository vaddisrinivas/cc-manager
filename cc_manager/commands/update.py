"""cc-manager update command."""
from __future__ import annotations
from typing import Optional
import typer
from rich.console import Console
from cc_manager.context import get_ctx, run_cmd
console = Console()
app = typer.Typer()

@app.command("update")
def update_cmd(name: Optional[str] = typer.Argument(None)) -> None:
    """Update installed tools (or a specific tool)."""
    ctx = get_ctx()
    tools = ctx.installed.get("tools", {})
    targets = {name: tools[name]} if name and name in tools else dict(tools)
    for tool_name, info in targets.items():
        if info.get("pinned"):
            console.print(f"[dim]Skipping pinned:[/dim] {tool_name}")
            continue
        reg = next((t for t in ctx.registry if t["name"] == tool_name), None)
        if not reg:
            continue
        for method in reg.get("install_methods", []):
            if method.get("type") in ("cargo","npm","go","pip","brew") and method.get("command"):
                rc, out = run_cmd(method["command"])
                status = "[green]updated[/green]" if rc == 0 else "[red]failed[/red]"
                console.print(f"{status}: {tool_name}")
                break
