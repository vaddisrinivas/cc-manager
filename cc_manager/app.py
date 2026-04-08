"""cc-manager Textual App — terminal and web dashboard."""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer
from textual.widgets import Footer, Static

from cc_manager import __version__
from cc_manager.dashboard_data import DashboardData
from cc_manager.widgets.header_bar import HeaderBar
from cc_manager.widgets.stats_bar import StatsBar
from cc_manager.widgets.token_chart import TokenChart
from cc_manager.widgets.cost_chart import CostChart
from cc_manager.widgets.tools_table import ToolsTable
from cc_manager.widgets.health_table import HealthTable
from cc_manager.widgets.sessions_table import SessionsTable
from cc_manager.widgets.event_log import EventLog
from cc_manager.widgets.recs_widget import RecsWidget


class CCManagerApp(App):
    """cc-manager full-screen dashboard."""

    TITLE = "cc-manager"
    CSS = """
    Screen {
        background: #0d1117;
        overflow-y: auto;
    }

    /* ── Row containers ──────────────────────────── */
    .charts-row {
        height: 16;
        layout: grid;
        grid-size: 2;
        grid-gutter: 1;
        margin: 1 1 0 1;
    }
    .tables-row {
        height: auto;
        layout: grid;
        grid-size: 2;
        grid-gutter: 1;
        margin: 1 1 0 1;
    }
    .full-row {
        margin: 1 1 0 1;
    }
    .recs-row {
        height: auto;
        margin: 1 1 0 1;
    }

    /* ── Widget borders / colours ────────────────── */
    TokenChart  { border: solid #58a6ff; }
    CostChart   { border: solid #bc8cff; }
    ToolsTable  { border: solid #58a6ff; min-height: 10; }
    HealthTable { border: solid #3fb950; min-height: 10; }
    SessionsTable { border: solid #58a6ff; }
    EventLog    { border: solid #444d56; }
    RecsWidget  { border: solid #d29922; }
    RecsWidget.all-clear { border: solid #3fb950; }

    /* ── StatsBar ────────────────────────────────── */
    StatsBar {
        background: #161b22;
        border-bottom: solid #30363d;
        padding: 0 2;
        height: 1;
    }

    /* ── DataTable tweaks ────────────────────────── */
    DataTable { background: #0d1117; }
    DataTable > .datatable--header { background: #161b22; color: #8b949e; }
    DataTable > .datatable--cursor { background: #1f6feb; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("R", "remove_tool", "Remove tool"),
        Binding("i", "install_prompt", "Install"),
        Binding("d", "run_doctor", "Doctor"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._data: DashboardData

    def compose(self) -> ComposeResult:
        yield HeaderBar()
        yield StatsBar()
        with ScrollableContainer():
            with Horizontal(classes="charts-row"):
                yield TokenChart()
                yield CostChart()
            yield RecsWidget(classes="recs-row")
            with Horizontal(classes="tables-row"):
                yield ToolsTable()
                yield HealthTable()
            yield SessionsTable(classes="full-row")
            yield EventLog(classes="full-row")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_data()
        self.set_interval(30, self._refresh_data)

    def _refresh_data(self) -> None:
        try:
            from cc_manager.dashboard_data import build_data
            self._data = build_data()
        except Exception:
            self._data = DashboardData(
                version=__version__, timestamp="error", status="DEGRADED",
                sessions=[], total_input=0, total_output=0, total_cost=0.0,
                total_tokens=0, avg_tokens_per_session=0, model_breakdown={},
                spark_values=[], spark_days=[], daily_cost={}, installed={},
                health_checks=[], cc_hooks=0, settings_ok=False,
                recs=[], available=[], events=[],
            )
        self._push_data()

    def _push_data(self) -> None:
        """Push current data to all widgets."""
        try:
            self.query_one(HeaderBar).update(self._data)
            self.query_one(StatsBar).update(self._data)
            self.query_one(TokenChart).update(self._data)
            self.query_one(CostChart).update(self._data)
            self.query_one(RecsWidget).update(self._data)
            self.query_one(ToolsTable).update(self._data)
            self.query_one(HealthTable).update(self._data)
            self.query_one(SessionsTable).update(self._data)
            self.query_one(EventLog).update(self._data)
        except Exception:
            pass

    # ── Actions ────────────────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        self._refresh_data()

    def action_remove_tool(self) -> None:
        table = self.query_one(ToolsTable)
        name = table.get_selected_tool()
        if not name:
            self.notify("Select a tool row first (↑↓)", severity="warning")
            return
        try:
            import cc_manager.context as ctx_mod
            ctx = ctx_mod.get_ctx()
            installed = ctx.installed.get("tools", {})
            if name not in installed:
                self.notify(f"{name} not found in installed list", severity="warning")
                return
            info = installed[name]
            if info.get("method") == "mcp":
                try:
                    import cc_manager.settings as settings_mod
                    settings_mod.remove_mcp(name)
                except Exception:
                    pass
            ctx.remove_installed(name)
            ctx.store.append("uninstall", tool=name)
            from cc_manager.context import invalidate_ctx
            invalidate_ctx()
            self.notify(f"✓ Removed {name}", severity="information")
            self._refresh_data()
        except Exception as exc:
            self.notify(f"Error removing {name}: {exc}", severity="error")

    def action_run_doctor(self) -> None:
        try:
            from cc_manager.commands.doctor import run_checks
            results = run_checks()
            n_ok = sum(1 for v in results.values() if v["status"] == "ok")
            n_fail = sum(1 for v in results.values() if v["status"] == "fail")
            n_warn = sum(1 for v in results.values() if v["status"] == "warn")
            self.notify(
                f"Doctor: {n_ok} ok · {n_warn} warn · {n_fail} fail",
                severity="information" if n_fail == 0 else "warning",
            )
            self._refresh_data()
        except Exception as exc:
            self.notify(f"Doctor error: {exc}", severity="error")

    def action_install_prompt(self) -> None:
        self.notify("Run: ccm install <tool-name>", severity="information")
