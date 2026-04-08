"""Stats bar — single-line summary widget."""
from __future__ import annotations
from rich.text import Text
from textual.widget import Widget
from textual.widgets import Static


class StatsBar(Widget):
    """One-liner stats bar: cost · sessions · tools · hooks · status."""
    DEFAULT_CSS = """
    StatsBar {
        height: 1;
        background: $surface;
        padding: 0 2;
        border-bottom: solid $primary-darken-2;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._content = Static("")

    def compose(self):
        yield self._content

    def update(self, data: dict) -> None:
        cost = data.get("total_cost", 0.0)
        sessions = len(data.get("sessions", []))
        n_tools = len(data.get("installed", {}))
        hooks = data.get("cc_hooks", 0)
        status = data.get("status", "NOMINAL")
        status_color = "green" if status == "NOMINAL" else "yellow"

        sep = Text("  ·  ", style="dim")
        line = Text()
        line.append("7d:", style="dim")
        line.append("  ")
        line.append(f"💰 ${cost:.4f}", style="green")
        line.append_text(sep)
        line.append(f"📊 {sessions} sessions", style="cyan")
        line.append_text(sep)
        line.append(f"🔧 {n_tools} tools", style="blue")
        line.append_text(sep)
        line.append(f"🪝 {hooks} hooks", style="magenta")
        line.append_text(sep)
        line.append(f"⚡ {status}", style=status_color)
        self._content.update(line)
