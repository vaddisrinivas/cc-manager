"""Event log DataTable widget."""
from __future__ import annotations
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Static
from cc_manager.context import fmt_tokens as abbrev


def _fmt_event_detail(e: dict) -> str:
    parts = []
    if e.get("input_tokens"):
        parts.append(abbrev(e["input_tokens"]) + " tokens")
    if e.get("cost_usd"):
        parts.append(f"${e['cost_usd']:.2f}")
    if e.get("duration_min"):
        parts.append(f"{e['duration_min']}m")
    if e.get("model"):
        parts.append(e["model"].replace("claude-", ""))
    if e.get("tool"):
        parts.append(e["tool"])
    if e.get("version"):
        parts.append(f"v{e['version']}")
    return " · ".join(parts) if parts else "—"


class EventLog(Widget):
    """Event log full-width table."""
    DEFAULT_CSS = """
    EventLog {
        height: auto;
        border: solid $primary;
        min-height: 8;
    }
    EventLog .evlog-title {
        color: $primary;
        text-style: bold;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._table = DataTable(id="events-dt", show_cursor=False)
        self._initialized = False

    def compose(self) -> ComposeResult:
        yield Static("⚡ EVENT LOG", classes="evlog-title")
        yield self._table

    def on_mount(self) -> None:
        self._table.add_columns("TIME", "EVENT", "DETAIL")
        self._initialized = True

    def update(self, data: dict) -> None:
        if not self._initialized:
            return
        self._table.clear()
        events = list(reversed(data.get("events", [])))
        if not events:
            self._table.add_row("[dim]No events recorded yet[/dim]", "", "")
            return
        for e in events[:15]:
            ts = (e.get("ts") or "")[:16].replace("T", " ")
            etype = (e.get("event") or "event").upper()
            detail = _fmt_event_detail(e)
            self._table.add_row(ts, etype, detail)
