"""cc-manager reset command."""
from __future__ import annotations
from typing import Optional
import typer
from rich.console import Console
console = Console()
app = typer.Typer()

@app.command("reset")
def reset_cmd(
    name: Optional[str] = typer.Argument(None),
    all_: bool = typer.Option(False, "--all"),
    config: bool = typer.Option(False, "--config"),
    confirm: bool = typer.Option(False, "--confirm"),
) -> None:
    """Reset a tool or entire cc-manager installation."""
    from cc_manager.context import get_ctx
    ctx = get_ctx()

    if config:
        if not confirm:
            console.print("Pass --confirm to reset config."); raise typer.Exit(1)
        import cc_manager.settings as s
        s.backup_create()
        from cc_manager.commands.init import DEFAULT_CONFIG
        import cc_manager.context as ctx_mod
        ctx_mod.CONFIG_PATH.write_text(DEFAULT_CONFIG, encoding="utf-8")
        console.print("[green]Config reset.[/green]"); return

    if all_:
        if not confirm:
            console.print("Pass --confirm to reset everything."); raise typer.Exit(1)
        from cc_manager.commands.init import run_init
        run_init(dry_run=False, minimal=True, yes=True)
        console.print("[green]Reset complete.[/green]"); return

    if name:
        from cc_manager.commands.install import install_tool, AlreadyInstalledError, ToolNotFoundError
        from cc_manager.commands.uninstall import uninstall_cmd
        try:
            install_tool(name, dry_run=False)
        except AlreadyInstalledError:
            console.print(f"[dim]{name} already installed.[/dim]")
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
