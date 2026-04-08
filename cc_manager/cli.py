"""cc-manager CLI entry point."""
from __future__ import annotations

import importlib
import functools

import typer
from rich.panel import Panel
from rich import box

from cc_manager import __version__

# ---------------------------------------------------------------------------
# Global error handler — no raw tracebacks, always a helpful hint
# ---------------------------------------------------------------------------
_ERROR_HINTS: dict[type, str] = {
    FileNotFoundError:  "hint: run [bright_cyan]ccm init[/bright_cyan] to create required directories",
    PermissionError:    "hint: check file permissions on [dim]~/.cc-manager/[/dim]",
    ValueError:         "hint: check the arguments you passed",
    ConnectionError:    "hint: check your internet connection",
}


def _rich_error(exc: BaseException, cmd: str = "") -> None:
    """Print a formatted error panel instead of a raw traceback."""
    from cc_manager.display import console
    hint = _ERROR_HINTS.get(type(exc), "run [bright_cyan]ccm doctor[/bright_cyan] for diagnostics")
    msg = str(exc).strip() or exc_type
    title = f"[bold bright_red]✗ {cmd or exc_type}[/bold bright_red]"
    body = f"  [bright_red]{msg}[/bright_red]"
    if hint:
        body += f"\n\n  [dim]{hint}[/dim]"
    console.print(Panel(body, title=title, border_style="bright_red", box=box.SIMPLE_HEAVY, padding=(0, 1)))


def _wrap(fn, cmd_name: str):
    """Wrap a command function to catch unhandled exceptions."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (typer.Exit, typer.Abort, SystemExit):
            raise
        except KeyboardInterrupt:
            from cc_manager.display import console
            console.print("\n  [dim]interrupted[/dim]")
            raise typer.Exit(130)
        except Exception as exc:
            _rich_error(exc, cmd_name)
            raise typer.Exit(1)
    return wrapper


app = typer.Typer(help="Claude Code ecosystem manager", no_args_is_help=False)

# ---------------------------------------------------------------------------
# Declarative command registry
# Each entry: (cli-name, module-path, function-name)
# ---------------------------------------------------------------------------
_COMMANDS: list[tuple[str, str, str]] = [
    ("init",        "cc_manager.commands.init",          "init_cmd"),
    ("install",     "cc_manager.commands.install",       "install_cmd"),
    ("uninstall",   "cc_manager.commands.uninstall",     "uninstall_cmd"),
    ("list",        "cc_manager.commands.list_cmd",      "list_cmd"),
    ("search",      "cc_manager.commands.search",        "search_cmd"),
    ("info",        "cc_manager.commands.info",          "info_cmd"),
    ("status",      "cc_manager.commands.status",        "status_cmd"),
    ("doctor",      "cc_manager.commands.doctor",        "doctor_cmd"),
    ("backup",      "cc_manager.commands.backup",        "backup_cmd"),
    ("config",      "cc_manager.commands.config",        "config_cmd"),
    ("update",      "cc_manager.commands.update",        "update_cmd"),
    ("pin",         "cc_manager.commands.pin",           "pin_cmd"),
    ("diff",        "cc_manager.commands.diff",          "diff_cmd"),
    ("audit",       "cc_manager.commands.audit",         "audit_cmd"),
    ("why",         "cc_manager.commands.why",           "why_cmd"),
    ("clean",       "cc_manager.commands.clean",         "clean_cmd"),
    ("logs",        "cc_manager.commands.logs",          "logs_cmd"),
    ("analyze",     "cc_manager.commands.analyze",       "analyze_cmd"),
    ("recommend",   "cc_manager.commands.recommend",     "recommend_cmd"),
    ("export",      "cc_manager.commands.export_import", "export_cmd"),
    ("import",      "cc_manager.commands.export_import", "import_cmd"),
    ("migrate",     "cc_manager.commands.migrate",       "migrate_cmd"),
    ("reset",       "cc_manager.commands.reset",         "reset_cmd"),
    ("completions", "cc_manager.commands.completions",   "completions_cmd"),
]

# Optional commands — silently skipped if module/symbol is missing
_OPTIONAL_COMMANDS: list[tuple[str, str, str]] = [
    ("dashboard", "cc_manager.commands.dashboard", "run"),
    ("tui",       "cc_manager.commands.tui",       "run"),
]

for _name, _mod_path, _fn_name in _COMMANDS:
    _mod = importlib.import_module(_mod_path)
    app.command(_name)(_wrap(getattr(_mod, _fn_name), _name))

for _name, _mod_path, _fn_name in _OPTIONAL_COMMANDS:
    try:
        _mod = importlib.import_module(_mod_path)
        app.command(_name)(_wrap(getattr(_mod, _fn_name), _name))
    except (ImportError, AttributeError):
        pass


# ---------------------------------------------------------------------------
# --version callback
# ---------------------------------------------------------------------------

def _version_callback(value: bool):
    if value:
        from cc_manager.display import console
        console.print(f"cc-manager v{__version__}")
        raise typer.Exit()


def _show_dashboard() -> None:
    """5-line at-a-glance summary when ccm is run with no args."""
    from cc_manager.display import console
    try:
        from cc_manager.context import get_ctx, get_week_stats
        ctx = get_ctx()
    except Exception:
        console.print(f"  [bold bright_cyan]cc-manager[/bold bright_cyan] [dim]v{__version__}[/dim]  — [dim]run[/dim] [bright_cyan]ccm init[/bright_cyan] [dim]to get started[/dim]")
        return

    installed_count = len(ctx.installed.get("tools", {}))
    recent, week_cost, _, _ = get_week_stats(ctx.store)
    last = recent[-1] if recent else None

    if last:
        ts   = last.get("ts", "")[:10]
        cost = last.get("cost_usd", 0.0)
        dur  = last.get("duration_min", 0)
        last_line = f"[dim]{ts}[/dim]  [bright_green]${cost:.4f}[/bright_green]  [dim]{dur}min[/dim]"
    else:
        last_line = "[dim]no sessions yet[/dim]"

    cc_hooks = sum(
        1 for entries in ctx.settings.get("hooks", {}).values()
        for entry in entries
        for h in entry.get("hooks", [])
        if ".cc-manager" in h.get("command", "")
    )
    health = "[bright_green]healthy[/bright_green]" if cc_hooks >= 2 else "[yellow]run ccm doctor[/yellow]"

    console.print()
    console.print(f"  [bold bright_cyan]◉ cc-manager[/bold bright_cyan] [dim]v{__version__}[/dim]")
    console.print(f"  [dim]tools[/dim]      [bright_white]{installed_count}[/bright_white] [dim]installed[/dim]")
    console.print(f"  [dim]this week[/dim]  [bright_green]${week_cost:.2f}[/bright_green]")
    console.print(f"  [dim]last run[/dim]   {last_line}")
    console.print(f"  [dim]health[/dim]     {health}")
    console.print()
    console.print(f"  [dim]Run[/dim] [bright_cyan]ccm --help[/bright_cyan] [dim]to see all commands.[/dim]")
    console.print()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    if ctx.invoked_subcommand is None:
        _show_dashboard()
