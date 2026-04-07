"""cc-manager CLI entry point."""
from __future__ import annotations

import typer

from cc_manager import __version__

app = typer.Typer(help="Claude Code ecosystem manager", no_args_is_help=True)

# Register commands — import the decorated function, register on main app
from cc_manager.commands.init import init_cmd
app.command("init")(init_cmd)

from cc_manager.commands.install import install_cmd
app.command("install")(install_cmd)

from cc_manager.commands.uninstall import uninstall_cmd
app.command("uninstall")(uninstall_cmd)

from cc_manager.commands.list_cmd import list_cmd
app.command("list")(list_cmd)

from cc_manager.commands.search import search_cmd
app.command("search")(search_cmd)

from cc_manager.commands.info import info_cmd
app.command("info")(info_cmd)

from cc_manager.commands.status import status_cmd
app.command("status")(status_cmd)

from cc_manager.commands.doctor import doctor_cmd
app.command("doctor")(doctor_cmd)

from cc_manager.commands.backup import backup_cmd
app.command("backup")(backup_cmd)

from cc_manager.commands.config import config_cmd
app.command("config")(config_cmd)

from cc_manager.commands.update import update_cmd
app.command("update")(update_cmd)

from cc_manager.commands.pin import pin_cmd
app.command("pin")(pin_cmd)

from cc_manager.commands.diff import diff_cmd
app.command("diff")(diff_cmd)

from cc_manager.commands.audit import audit_cmd
app.command("audit")(audit_cmd)

from cc_manager.commands.why import why_cmd
app.command("why")(why_cmd)

from cc_manager.commands.clean import clean_cmd
app.command("clean")(clean_cmd)

from cc_manager.commands.logs import logs_cmd
app.command("logs")(logs_cmd)

from cc_manager.commands.analyze import analyze_cmd
app.command("analyze")(analyze_cmd)

from cc_manager.commands.recommend import recommend_cmd
app.command("recommend")(recommend_cmd)

from cc_manager.commands.export_import import export_cmd, import_cmd
app.command("export")(export_cmd)
app.command("import")(import_cmd)

from cc_manager.commands.migrate import migrate_cmd
app.command("migrate")(migrate_cmd)

from cc_manager.commands.reset import reset_cmd
app.command("reset")(reset_cmd)

from cc_manager.commands.completions import completions_cmd
app.command("completions")(completions_cmd)

# Optional modules
try:
    from cc_manager.commands.serve import run as serve_run
    app.command("serve")(serve_run)
except ImportError:
    pass

try:
    from cc_manager.commands.dashboard import run as dashboard_run
    app.command("dashboard")(dashboard_run)
except ImportError:
    pass

try:
    from cc_manager.commands.tui import run as tui_run
    app.command("tui")(tui_run)
except ImportError:
    pass


def version_callback(value: bool):
    if value:
        from cc_manager.display import console
        console.print(f"cc-manager v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", callback=version_callback, is_eager=True,
        help="Show version and exit."
    )
):
    pass
