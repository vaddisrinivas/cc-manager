"""cc-manager CLI entry point."""
from __future__ import annotations

import typer
from rich.console import Console

from cc_manager import __version__

app = typer.Typer(help="Claude Code ecosystem manager", no_args_is_help=True)
console = Console()

# Register all commands
from cc_manager.commands.init import app as _init_app
app.add_typer(_init_app, name="init")

from cc_manager.commands.install import app as _install_app
app.add_typer(_install_app, name="install")

from cc_manager.commands.uninstall import app as _uninstall_app
app.add_typer(_uninstall_app, name="uninstall")

from cc_manager.commands.list_cmd import app as _list_app
app.add_typer(_list_app, name="list")

from cc_manager.commands.search import app as _search_app
app.add_typer(_search_app, name="search")

from cc_manager.commands.info import app as _info_app
app.add_typer(_info_app, name="info")

from cc_manager.commands.status import app as _status_app
app.add_typer(_status_app, name="status")

from cc_manager.commands.doctor import app as _doctor_app
app.add_typer(_doctor_app, name="doctor")

from cc_manager.commands.backup import app as _backup_app
app.add_typer(_backup_app, name="backup")

from cc_manager.commands.config import app as _config_app
app.add_typer(_config_app, name="config")

from cc_manager.commands.update import app as _update_app
app.add_typer(_update_app, name="update")

from cc_manager.commands.pin import app as _pin_app
app.add_typer(_pin_app, name="pin")

from cc_manager.commands.diff import app as _diff_app
app.add_typer(_diff_app, name="diff")

from cc_manager.commands.audit import app as _audit_app
app.add_typer(_audit_app, name="audit")

from cc_manager.commands.why import app as _why_app
app.add_typer(_why_app, name="why")

from cc_manager.commands.clean import app as _clean_app
app.add_typer(_clean_app, name="clean")

from cc_manager.commands.logs import app as _logs_app
app.add_typer(_logs_app, name="logs")

from cc_manager.commands.analyze import app as _analyze_app
app.add_typer(_analyze_app, name="analyze")

from cc_manager.commands.recommend import app as _recommend_app
app.add_typer(_recommend_app, name="recommend")

from cc_manager.commands.export_import import app as _export_import_app
app.add_typer(_export_import_app, name="export-import")

from cc_manager.commands.migrate import app as _migrate_app
app.add_typer(_migrate_app, name="migrate")

from cc_manager.commands.reset import app as _reset_app
app.add_typer(_reset_app, name="reset")

from cc_manager.commands.completions import app as _completions_app
app.add_typer(_completions_app, name="completions")

# Gracefully handle optional modules
try:
    from cc_manager.commands import serve
    app.command()(serve.run)
except ImportError:
    pass

try:
    from cc_manager.commands import dashboard as dashboard_cmd
    app.command()(dashboard_cmd.run)
except ImportError:
    pass

try:
    from cc_manager.commands.tui import app as _tui_app
    app.add_typer(_tui_app, name="tui")
except ImportError:
    pass


def version_callback(value: bool):
    if value:
        from cc_manager.display import console, header
        header(f"cc-manager v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", callback=version_callback, is_eager=True,
        help="Show version and exit."
    )
):
    pass
