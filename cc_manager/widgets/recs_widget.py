"""Recommendations panel widget."""
from __future__ import annotations
from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


class RecsWidget(Widget):
    """Compact recommendations panel — one line per suggestion."""
    DEFAULT_CSS = """
    RecsWidget {
        height: auto;
        border: solid $warning-darken-2;
        padding: 0 1;
    }
    RecsWidget.all-clear {
        border: solid $success-darken-2;
        display: none;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._content = Static("")

    def compose(self) -> ComposeResult:
        yield self._content

    def update(self, data: dict) -> None:
        recs = data.get("recs", [])
        if not recs:
            self.add_class("all-clear")
            self._content.update("")
            return

        self.remove_class("all-clear")
        lines = Text()
        for i, r in enumerate(recs[:4]):
            if i:
                lines.append("\n")
            tool = r.get("tool")
            msg = r.get("message", "")
            cmd = r.get("install_cmd")
            lines.append("  · ", style="dim")
            if tool:
                lines.append(tool, style="bright_white")
                lines.append("  ", style="")
            lines.append(msg, style="dim")
            if cmd:
                lines.append("  ")
                lines.append(cmd, style="cyan")

        extra = len(recs) - 4
        if extra > 0:
            lines.append(f"\n  · ", style="dim")
            lines.append(f"+{extra} more", style="dim")
            lines.append("  ccm recommend", style="dim")

        self._content.update(lines)
