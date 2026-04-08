"""Health checks widget."""
from __future__ import annotations
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Static

from cc_manager.theme import status_label


class HealthTable(Widget):
    """Health check results panel."""
    DEFAULT_CSS = """
    HealthTable {
        height: auto;
        border: solid $success;
        min-height: 8;
    }
    HealthTable .health-title {
        color: $success;
        text-style: bold;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._table = DataTable(id="health-dt", show_cursor=False)
        self._initialized = False

    def compose(self) -> ComposeResult:
        yield Static("⚡ HEALTH  [dim](D doctor)[/dim]", classes="health-title")
        yield self._table

    def on_mount(self) -> None:
        self._table.add_columns("CHECK", "STATUS", "DETAIL")
        self._initialized = True

    def update(self, data: dict) -> None:
        if not self._initialized:
            return
        self._table.clear()
        settings_ok = data.get("settings_ok", False)
        cc_hooks = data.get("cc_hooks", 0)

        self._table.add_row(
            "settings.json",
            status_label("ok" if settings_ok else "fail"),
            "loaded",
        )
        hooks_status = "ok" if cc_hooks >= 2 else "warn" if cc_hooks > 0 else "fail"
        self._table.add_row("hooks", status_label(hooks_status), f"{cc_hooks} registered")

        for name, st, detail in data.get("health_checks", []):
            self._table.add_row(name, status_label(st), detail[:36] if detail else "")
