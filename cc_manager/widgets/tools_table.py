"""Installed tools DataTable widget."""
from __future__ import annotations
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Static

from cc_manager.theme import status_label


class ToolsTable(Widget):
    """DataTable of installed tools. Selected row can be removed via 'R' key."""
    DEFAULT_CSS = """
    ToolsTable {
        height: auto;
        border: solid $primary;
        min-height: 8;
    }
    ToolsTable .tools-title {
        color: $primary;
        text-style: bold;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._table = DataTable(cursor_type="row", id="tools-dt")
        self._initialized = False

    def compose(self) -> ComposeResult:
        yield Static("⚡ INSTALLED TOOLS  [dim](↑↓ select · R remove)[/dim]", classes="tools-title")
        yield self._table

    def on_mount(self) -> None:
        self._table.add_columns("TOOL", "VERSION", "METHOD", "STATUS")
        self._initialized = True

    def update(self, data: dict) -> None:
        if not self._initialized:
            return
        self._table.clear()
        installed = data.get("installed", {})
        checks = {name: st for name, st, _ in data.get("health_checks", [])}
        if not installed:
            self._table.add_row("[dim]No tools installed[/dim]", "", "", "")
            return
        for name, meta in installed.items():
            st = checks.get(name, "ok")
            self._table.add_row(
                f"✓ {name}",
                meta.get("version", "--"),
                meta.get("method", "--"),
                status_label(st),
            )

    def get_selected_tool(self) -> str | None:
        """Return the tool name of the currently highlighted row, or None."""
        try:
            cell = self._table.get_cell_at(self._table.cursor_coordinate)
            name = str(cell).lstrip("✓ ").strip()
            return name if name and name != "No tools installed" else None
        except Exception:
            return None
