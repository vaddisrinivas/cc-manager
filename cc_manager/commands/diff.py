"""cc-manager diff command."""
from __future__ import annotations
import json
import typer
from rich.console import Console
import cc_manager.settings as settings_mod
from cc_manager.context import get_ctx
console = Console()
app = typer.Typer()

def _recursive_diff(old, new, path=""):
    changes = []
    if isinstance(old, dict) and isinstance(new, dict):
        all_keys = set(old) | set(new)
        for k in sorted(all_keys):
            p = f"{path}.{k}" if path else k
            if k not in old:
                changes.append(("added", p, None, new[k]))
            elif k not in new:
                changes.append(("removed", p, old[k], None))
            else:
                changes.extend(_recursive_diff(old[k], new[k], p))
    elif old != new:
        changes.append(("changed", path, old, new))
    return changes

@app.command("diff")
def diff_cmd() -> None:
    """Show diff between latest backup and current settings.json."""
    backups = settings_mod.backup_list()
    if not backups:
        console.print("No backups found."); return
    latest_backup = backups[-1]
    old = json.loads(latest_backup.read_text(encoding="utf-8"))
    new = settings_mod.read()
    changes = _recursive_diff(old, new)
    if not changes:
        console.print("[green]No changes.[/green]"); return
    for kind, path, old_val, new_val in changes:
        if kind == "added":
            console.print(f"[green]+ {path}: {new_val!r}[/green]")
        elif kind == "removed":
            console.print(f"[red]- {path}: {old_val!r}[/red]")
        else:
            console.print(f"[yellow]~ {path}: {old_val!r} → {new_val!r}[/yellow]")
