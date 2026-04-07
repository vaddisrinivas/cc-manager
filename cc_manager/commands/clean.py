"""cc-manager clean command."""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from cc_manager.context import get_ctx
console = Console()
app = typer.Typer()

@app.command("clean")
def clean_cmd(
    sessions: bool = typer.Option(False, "--sessions"),
    backups: bool = typer.Option(False, "--backups"),
    all_: bool = typer.Option(False, "--all"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    older_than: str = typer.Option("30d", "--older-than"),
    keep_last: int = typer.Option(5, "--keep-last"),
) -> None:
    """Clean old sessions or backups."""
    from cc_manager.context import parse_duration, MANAGER_DIR
    import cc_manager.settings as settings_mod
    from datetime import datetime, timezone
    ctx = get_ctx()

    if sessions or all_:
        try:
            td = parse_duration(older_than)
        except ValueError:
            td = __import__("datetime").timedelta(days=30)
        cutoff = datetime.now(timezone.utc) - td
        deleted = 0; freed = 0
        claude_projects = Path.home() / ".claude" / "projects"
        if claude_projects.exists():
            for jsonl in claude_projects.rglob("*.jsonl"):
                if jsonl.stat().st_mtime < cutoff.timestamp():
                    size = jsonl.stat().st_size
                    if dry_run:
                        console.print(f"Would delete: {jsonl} ({size} bytes)")
                    else:
                        jsonl.unlink()
                    deleted += 1; freed += size
        ctx.store.append("clean", deleted_sessions=deleted, freed_bytes=freed)
        console.print(f"Cleaned {deleted} sessions, freed {freed} bytes")

    if backups or all_:
        all_backups = settings_mod.backup_list()
        to_remove = all_backups[:-keep_last] if len(all_backups) > keep_last else []
        for b in to_remove:
            if dry_run:
                console.print(f"Would delete backup: {b.name}")
            else:
                b.unlink()
        console.print(f"Removed {len(to_remove)} old backups")
