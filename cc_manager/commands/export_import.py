"""cc-manager export/import command."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from cc_manager import __version__
from cc_manager.context import get_ctx
import cc_manager.context as ctx_mod
console = Console()
app = typer.Typer()

@app.command("export")
def export_cmd(output: Optional[Path] = typer.Option(None, "--output", "-o")) -> None:
    """Export installed tools and config."""
    ctx = get_ctx()
    data = {
        "schema_version": 1,
        "cc_manager_version": __version__,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "config": ctx.config,
        "tools": list(ctx.installed.get("tools", {}).keys()),
    }
    text = json.dumps(data, indent=2)
    if output:
        output.write_text(text, encoding="utf-8")
        console.print(f"[green]Exported to[/green] {output}")
    else:
        console.print(text)

@app.command("import")
def import_cmd(
    file: Path = typer.Argument(...),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Import from an export file."""
    data = json.loads(file.read_text(encoding="utf-8"))
    tools = data.get("tools", [])
    from cc_manager.commands.install import install_tool, AlreadyInstalledError, ToolNotFoundError
    for name in tools:
        if dry_run:
            console.print(f"Would install: {name}"); continue
        try:
            install_tool(name, dry_run=False)
            console.print(f"[green]Installed[/green] {name}")
        except AlreadyInstalledError:
            console.print(f"[dim]Already installed:[/dim] {name}")
        except (ToolNotFoundError, Exception) as e:
            console.print(f"[yellow]Skipped {name}: {e}[/yellow]")
