"""Recent sessions DataTable widget."""
from __future__ import annotations
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Static
from cc_manager.commands.tui import abbrev


class SessionsTable(Widget):
    """Recent sessions full-width table."""
    DEFAULT_CSS = """
    SessionsTable {
        height: auto;
        min-height: 10;
        border: solid $primary;
    }
    SessionsTable .sess-title {
        color: $primary;
        text-style: bold;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._table = DataTable(id="sessions-dt", show_cursor=False)
        self._initialized = False

    def compose(self) -> ComposeResult:
        yield Static("⚡ RECENT SESSIONS  [dim](7d · most recent first)[/dim]", classes="sess-title")
        yield self._table

    def on_mount(self) -> None:
        self._table.add_columns("TIME", "MODEL", "DUR", "IN TOKENS", "OUT TOKENS", "COST")
        self._initialized = True

    def update(self, data: dict) -> None:
        if not self._initialized:
            return
        self._table.clear()
        sessions = data.get("sessions", [])
        if not sessions:
            self._table.add_row("[dim]No sessions recorded yet[/dim]", "", "", "", "", "")
            return
        for s in list(reversed(sessions[-10:])):
            ts = (s.get("ts") or "")[:16].replace("T", " ")
            model = s.get("model", "--").replace("claude-", "").replace("-latest", "")
            dur = f"{s.get('duration_min')}m" if s.get("duration_min") is not None else "--"
            inp = abbrev(s.get("input_tokens", 0))
            out = abbrev(s.get("output_tokens", 0))
            cost = f"[green]${s.get('cost_usd', 0.0):.4f}[/green]"
            self._table.add_row(ts, model[:16], dur, inp, out, cost)
