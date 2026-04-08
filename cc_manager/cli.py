"""cc-manager CLI entry point."""
from __future__ import annotations

import importlib

import typer

from cc_manager import __version__

app = typer.Typer(help="Claude Code ecosystem manager", no_args_is_help=True)

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
    ("serve",     "cc_manager.commands.serve",     "run"),
    ("dashboard", "cc_manager.commands.dashboard", "run"),
    ("tui",       "cc_manager.commands.tui",       "run"),
]

for _name, _mod_path, _fn_name in _COMMANDS:
    _mod = importlib.import_module(_mod_path)
    app.command(_name)(getattr(_mod, _fn_name))

for _name, _mod_path, _fn_name in _OPTIONAL_COMMANDS:
    try:
        _mod = importlib.import_module(_mod_path)
        app.command(_name)(getattr(_mod, _fn_name))
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


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    )
):
    pass
