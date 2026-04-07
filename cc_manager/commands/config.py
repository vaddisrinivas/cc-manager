"""cc-manager config command."""
from __future__ import annotations
import os, subprocess, tomllib
import typer
import tomli_w
from rich.console import Console
from cc_manager.context import get_ctx
import cc_manager.context as ctx_mod
console = Console()
app = typer.Typer()

def _dot_get(data: dict, key: str):
    parts = key.split(".")
    val = data
    for p in parts:
        if isinstance(val, dict):
            val = val.get(p)
        else:
            return None
    return val

def _dot_set(data: dict, key: str, value) -> dict:
    parts = key.split(".")
    d = data
    for p in parts[:-1]:
        d = d.setdefault(p, {})
    d[parts[-1]] = value
    return data

@app.command("config-get")
def config_get_cmd(key: str = typer.Argument(...)) -> None:
    """Get a config value by dot-notation key."""
    ctx = get_ctx()
    val = _dot_get(ctx.config, key)
    console.print(f"{key} = {val!r}")

@app.command("config-set")
def config_set_cmd(key: str = typer.Argument(...), value: str = typer.Argument(...)) -> None:
    """Set a config value."""
    ctx = get_ctx()
    # Try to coerce value type
    for coerce in (int, float):
        try:
            value = coerce(value)
            break
        except ValueError:
            pass
    _dot_set(ctx.config, key, value)
    p = ctx_mod.CONFIG_PATH
    p.write_bytes(tomli_w.dumps(ctx.config).encode())
    console.print(f"[green]Set[/green] {key} = {value!r}")

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
    s.backup_create()
    from cc_manager.commands.init import DEFAULT_CONFIG
    ctx_mod.CONFIG_PATH.write_text(DEFAULT_CONFIG, encoding="utf-8")
    console.print("[green]Config reset to defaults.[/green]")


# Alias for cli.py import
config_cmd = config_get_cmd
