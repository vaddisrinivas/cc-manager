"""cc-manager backup command."""
from __future__ import annotations
import typer
from rich import box
from rich.panel import Panel
from rich.padding import Padding
from rich.rule import Rule

import cc_manager.settings as settings_mod
from cc_manager.display import console, success, error, info

app = typer.Typer()


@app.command("backup-create")
def backup_create_cmd() -> None:
    """Create a backup of settings.json."""
    console.print()
    info("Backing up [dim]settings.json[/dim]...")
    p = settings_mod.backup_create()

    try:
        size_bytes = p.stat().st_size if p.exists() else 0
        if size_bytes >= 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes} bytes"
    except Exception:
        size_str = "—"

    console.print()
    console.print(Rule(style="bright_green"))
    success("Snapshot created:")
    console.print(f"    [dim]{p}[/dim]")
    console.print(f"    [dim]Size:[/dim] [bright_white]{size_str}[/bright_white]")
    console.print(Rule(style="bright_green"))
    console.print()


@app.command("backup-list")
def backup_list_cmd() -> None:
    """List all settings backups."""
    backups = settings_mod.backup_list()
    console.print()
    if not backups:
        console.print(
            Panel(
                "  [dim]No backups found.[/dim]\n\n"
                "  [dim]Run [bright_cyan]ccm backup-create[/bright_cyan] to create one.[/dim]",
                title="[bold bright_cyan]◆ BACKUPS[/bold bright_cyan]",
                border_style="cyan",
                box=box.SIMPLE_HEAVY,
                padding=(0, 1),
            )
        )
        console.print()
        return

    lines = []
    for b in backups:
        size = b.stat().st_size if b.exists() else 0
        if size >= 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size} bytes"
        lines.append(
            f"  [bright_cyan]◆[/bright_cyan]  [bright_white]{b.name}[/bright_white]  [dim]({size_str})[/dim]"
        )

    console.print(
        Panel(
            "\n".join(lines),
            title=f"[bold bright_cyan]◆ BACKUPS[/bold bright_cyan]  [dim]({len(backups)} found)[/dim]",
            border_style="cyan",
            box=box.SIMPLE_HEAVY,
            padding=(0, 1),
        )
    )
    console.print()


@app.command("backup-restore")
def backup_restore_cmd(timestamp: str = typer.Argument(..., help="Backup timestamp")) -> None:
    """Restore a settings backup."""
    console.print()
    info(f"Restoring backup [bright_white]{timestamp}[/bright_white]...")
    settings_mod.backup_restore(timestamp)
    console.print()
    success(f"Restored backup: [dim]{timestamp}[/dim]")
    console.print()


# Alias for cli.py import
backup_cmd = backup_create_cmd
