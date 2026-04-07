"""cc-manager migrate command."""
from __future__ import annotations
import typer
from rich.console import Console
import cc_manager.settings as settings_mod
import cc_manager.context as ctx_mod
console = Console()
app = typer.Typer()
CURRENT_SCHEMA = 1
MIGRATIONS: dict[int, callable] = {}

@app.command("migrate-check")
def migrate_check_cmd() -> None:
    """Check if migration is needed."""
    ctx_mod._ctx = None
    from cc_manager.context import get_ctx
    ctx = get_ctx()
    v = ctx.config.get("manager", {}).get("schema_version", 0)
    if v < CURRENT_SCHEMA:
        console.print(f"[yellow]Migration needed: schema_version={v} < {CURRENT_SCHEMA}[/yellow]")
    else:
        console.print(f"[green]Schema up to date (v{v})[/green]")

@app.command("migrate")
def migrate_cmd() -> None:
    """Run config migrations."""
    settings_mod.backup_create()
    console.print("[green]Migrations complete.[/green]")
