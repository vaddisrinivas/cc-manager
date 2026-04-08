"""Header bar widget."""
from __future__ import annotations
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


class HeaderBar(Widget):
    """Top header: version, status badge, last-updated time."""
    DEFAULT_CSS = """
    HeaderBar {
        height: 3;
        background: $surface;
        border-bottom: solid $primary;
        padding: 0 2;
        layout: horizontal;
        align: left middle;
    }
    HeaderBar .title { color: $primary; text-style: bold; }
    HeaderBar .status-ok { color: $success; }
    HeaderBar .status-degraded { color: $warning; }
    HeaderBar .ts { color: $text-muted; dock: right; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._data: dict = {}

    def compose(self) -> ComposeResult:
        yield Static("", id="hb-title", classes="title")
        yield Static("", id="hb-status")
        yield Static("", id="hb-ts", classes="ts")

    def update(self, data: dict) -> None:
        self._data = data
        v = data.get("version", "?")
        status = data.get("status", "NOMINAL")
        ts = data.get("timestamp", "")
        self.query_one("#hb-title", Static).update(
            f"◉ CC-MANAGER  v{v}  ·  Claude Code Ecosystem Controller"
        )
        cls = "status-ok" if status == "NOMINAL" else "status-degraded"
        dot = "●" if status == "NOMINAL" else "⚠"
        self.query_one("#hb-status", Static).update(
            f"  [{cls}]{dot} {status}[/{cls}]"
        )
        self.query_one("#hb-ts", Static).update(f"Updated {ts}")
