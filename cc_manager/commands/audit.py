"""cc-manager audit command."""
from __future__ import annotations
import typer
from rich.console import Console
from rich.table import Table
import cc_manager.settings as settings_mod
console = Console()
app = typer.Typer()

@app.command("audit")
def audit_cmd() -> None:
    """Audit settings.json for ownership of hooks and MCP servers."""
    data = settings_mod.read()
    table = Table(title="settings.json Audit")
    table.add_column("Type"); table.add_column("Name"); table.add_column("Owner")

    for ev, entries in data.get("hooks", {}).items():
        for entry in entries:
            for h in entry.get("hooks", []):
                cmd = h.get("command","")
                owner = "cc-manager" if ".cc-manager" in cmd else ("rtk" if "rtk" in cmd else "user")
                table.add_row("hook", ev, owner)

    for name in data.get("mcpServers", {}):
        table.add_row("mcp", name, "cc-manager")

    for p in data.get("enabledPlugins", []):
        table.add_row("plugin", p, "user")

    console.print(table)
