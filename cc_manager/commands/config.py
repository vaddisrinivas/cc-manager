"""cc-manager config command."""
from __future__ import annotations
import os
import subprocess
import tomllib

import typer
import tomli_w
from rich.console import Console

import cc_manager.context as ctx_mod
from cc_manager.context import get_ctx
from cc_manager.context import dot_get, dot_set

console = Console()
app = typer.Typer()


@app.command("config-get")
def config_get_cmd(key: str = typer.Argument(...)) -> None:
    """Get a config value by dot-notation key."""
    ctx = get_ctx()
    val = dot_get(ctx.config, key)
    console.print(f"{key} = {val!r}")


@app.command("config-set")
def config_set_cmd(key: str = typer.Argument(...), value: str = typer.Argument(...)) -> None:
    """Set a config value."""
    ctx = get_ctx()
    # Coerce numeric strings to int/float where possible
    coerced: str | int | float = value
    for cast in (int, float):
        try:
            coerced = cast(value)
            break
        except ValueError:
            pass
    dot_set(ctx.config, key, coerced)
    ctx_mod.CONFIG_PATH.write_bytes(tomli_w.dumps(ctx.config).encode())
    console.print(f"[green]Set[/green] {key} = {coerced!r}")


@app.command("config-edit")
def config_edit_cmd() -> None:
    """Open config.toml in editor."""
    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, str(ctx_mod.CONFIG_PATH)])


@app.command("config-reset")
def config_reset_cmd(confirm: bool = typer.Option(False, "--confirm")) -> None:
    """Reset config.toml to defaults (backup first)."""
    if not confirm:
        console.print("Pass --confirm to reset config.")
        raise typer.Exit(1)
    import cc_manager.settings as s
    from cc_manager.config import cfg
    s.backup_create()
    ctx_mod.CONFIG_PATH.write_text(cfg.to_toml(), encoding="utf-8")
    console.print("[green]Config reset to defaults.[/green]")


# Alias for cli.py import
config_cmd = config_get_cmd
