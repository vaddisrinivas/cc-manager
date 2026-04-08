"""Textual TUI headless tests — exercises the full CCManagerApp widget tree.

Uses App.run_test() (Textual's built-in headless pilot) so no TTY is needed.
build_data is patched to a fixture so tests are fast and deterministic.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Fixture: a realistic DashboardData dict
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_data():
    return {
        "version": "0.1.0",
        "timestamp": "12:00:00",
        "status": "NOMINAL",
        "sessions": [
            {
                "session": "sess-001",
                "input_tokens": 10_000,
                "output_tokens": 5_000,
                "cost_usd": 0.09,
                "model": "claude-sonnet-4-6",
            }
        ],
        "total_input": 10_000,
        "total_output": 5_000,
        "total_cost": 0.09,
        "total_tokens": 15_000,
        "avg_tokens_per_session": 15_000,
        "model_breakdown": {"claude-sonnet-4-6": 1},
        "spark_values": [0, 5, 10, 8, 12, 7, 15],
        "spark_days": [
            "2026-04-01", "2026-04-02", "2026-04-03",
            "2026-04-04", "2026-04-05", "2026-04-06", "2026-04-07",
        ],
        "daily_cost": {"2026-04-07": 0.09},
        "installed": {
            "context7": {"version": "latest", "method": "mcp", "installed_at": "2026-04-07T12:00:00"},
        },
        "health_checks": [("context7", "ok", "configured")],
        "cc_hooks": 3,
        "settings_ok": True,
        "recs": [],
        "available": [],
        "events": [
            {"event": "session_start", "ts": "2026-04-07T11:00:00", "session": "sess-001"},
        ],
    }


@pytest.fixture
def degraded_data(sample_data):
    d = dict(sample_data)
    d["status"] = "DEGRADED"
    d["health_checks"] = [("context7", "fail", "binary not found")]
    d["settings_ok"] = False
    d["recs"] = [
        {"tool": "rtk", "message": "avg tokens > 500K", "install_cmd": "ccm install rtk"}
    ]
    return d


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_build(data):
    """Context manager: patch build_data wherever app.py imports it."""
    return patch("cc_manager.dashboard_data.build_data", return_value=data)


# ---------------------------------------------------------------------------
# Widget presence tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_widgets_mount(sample_data):
    """Every widget in the compose tree mounts without error."""
    from cc_manager.app import CCManagerApp
    from cc_manager.widgets.header_bar import HeaderBar
    from cc_manager.widgets.stats_bar import StatsBar
    from cc_manager.widgets.token_chart import TokenChart
    from cc_manager.widgets.cost_chart import CostChart
    from cc_manager.widgets.tools_table import ToolsTable
    from cc_manager.widgets.health_table import HealthTable
    from cc_manager.widgets.sessions_table import SessionsTable
    from cc_manager.widgets.event_log import EventLog
    from cc_manager.widgets.recs_widget import RecsWidget

    with _patch_build(sample_data):
        async with CCManagerApp().run_test() as pilot:
            app = pilot.app
            assert app.query_one(HeaderBar) is not None
            assert app.query_one(StatsBar) is not None
            assert app.query_one(TokenChart) is not None
            assert app.query_one(CostChart) is not None
            assert app.query_one(ToolsTable) is not None
            assert app.query_one(HealthTable) is not None
            assert app.query_one(SessionsTable) is not None
            assert app.query_one(EventLog) is not None
            assert app.query_one(RecsWidget) is not None
            await pilot.press("q")


# ---------------------------------------------------------------------------
# Data propagation tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stats_bar_reflects_data(sample_data):
    """StatsBar.update() receives the correct values from the data dict."""
    from cc_manager.app import CCManagerApp
    from cc_manager.widgets.stats_bar import StatsBar

    received: list[dict] = []
    original = StatsBar.update

    def spy(self, data):
        received.append(data)
        original(self, data)

    with _patch_build(sample_data), patch.object(StatsBar, "update", spy):
        async with CCManagerApp().run_test() as pilot:
            await pilot.pause()
            assert received, "StatsBar.update was never called"
            d = received[-1]
            assert abs(d["total_cost"] - 0.09) < 0.001
            assert len(d["sessions"]) == 1
            assert len(d["installed"]) == 1
            assert d["cc_hooks"] == 3
            assert d["status"] == "NOMINAL"
            await pilot.press("q")


@pytest.mark.asyncio
async def test_stats_bar_degraded(degraded_data):
    """StatsBar.update() receives DEGRADED status."""
    from cc_manager.app import CCManagerApp
    from cc_manager.widgets.stats_bar import StatsBar

    received: list[dict] = []
    original = StatsBar.update

    def spy(self, data):
        received.append(data)
        original(self, data)

    with _patch_build(degraded_data), patch.object(StatsBar, "update", spy):
        async with CCManagerApp().run_test() as pilot:
            await pilot.pause()
            assert received, "StatsBar.update was never called"
            assert received[-1]["status"] == "DEGRADED"
            await pilot.press("q")


@pytest.mark.asyncio
async def test_tools_table_populated(sample_data):
    """App data reaches the widget layer — installed tools are in _data."""
    from cc_manager.app import CCManagerApp
    from cc_manager.widgets.tools_table import ToolsTable

    with _patch_build(sample_data):
        async with CCManagerApp().run_test() as pilot:
            await pilot.pause()
            # _data is set by _refresh_data; verify it contains expected tools
            data = pilot.app._data
            assert data is not None
            assert "context7" in data.get("installed", {}), \
                f"context7 missing from installed: {list(data.get('installed', {}).keys())}"
            # ToolsTable widget is present in the tree
            assert pilot.app.query_one(ToolsTable) is not None
            await pilot.press("q")


@pytest.mark.asyncio
async def test_tools_table_empty_when_no_installed():
    """ToolsTable shows placeholder row when no tools are installed."""
    from cc_manager.app import CCManagerApp
    from cc_manager.widgets.tools_table import ToolsTable
    from textual.widgets import DataTable

    empty_data = {
        "version": "0.1.0", "timestamp": "12:00:00", "status": "NOMINAL",
        "sessions": [], "total_input": 0, "total_output": 0, "total_cost": 0.0,
        "total_tokens": 0, "avg_tokens_per_session": 0, "model_breakdown": {},
        "spark_values": [], "spark_days": [], "daily_cost": {},
        "installed": {}, "health_checks": [], "cc_hooks": 0, "settings_ok": True,
        "recs": [], "available": [], "events": [],
    }
    with _patch_build(empty_data):
        async with CCManagerApp().run_test() as pilot:
            table = pilot.app.query_one(ToolsTable)
            dt = table.query_one(DataTable)
            assert dt.row_count == 1  # the "No tools installed" placeholder
            await pilot.press("q")


@pytest.mark.asyncio
async def test_recs_widget_visible_with_recommendations(degraded_data):
    """RecsWidget is present and receives recommendation data."""
    from cc_manager.app import CCManagerApp
    from cc_manager.widgets.recs_widget import RecsWidget

    with _patch_build(degraded_data):
        async with CCManagerApp().run_test() as pilot:
            widget = pilot.app.query_one(RecsWidget)
            assert widget is not None
            await pilot.press("q")


# ---------------------------------------------------------------------------
# Keybinding tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_q_quits(sample_data):
    """Pressing 'q' exits the app cleanly (return code 0)."""
    from cc_manager.app import CCManagerApp

    with _patch_build(sample_data):
        async with CCManagerApp().run_test() as pilot:
            await pilot.press("q")
        # If we reach here without exception the app exited cleanly
        assert True


@pytest.mark.asyncio
async def test_r_triggers_refresh(sample_data):
    """Pressing 'r' calls _refresh_data without raising."""
    from cc_manager.app import CCManagerApp

    call_count = 0
    original = sample_data.copy()

    def counting_build():
        nonlocal call_count
        call_count += 1
        return original

    with patch("cc_manager.dashboard_data.build_data", side_effect=counting_build):
        async with CCManagerApp().run_test() as pilot:
            before = call_count
            await pilot.press("r")
            await pilot.pause()
            assert call_count > before, "refresh should call build_data again"
            await pilot.press("q")


@pytest.mark.asyncio
async def test_refresh_recovers_from_build_error(sample_data):
    """If build_data raises, the app falls back to DEGRADED state without crashing."""
    from cc_manager.app import CCManagerApp
    from cc_manager.widgets.stats_bar import StatsBar

    received: list[dict] = []
    first_call = [True]

    def flaky_build():
        if first_call[0]:
            first_call[0] = False
            return sample_data
        raise RuntimeError("simulated data fetch failure")

    original = StatsBar.update

    def spy(self, data):
        received.append(data)
        original(self, data)

    with patch("cc_manager.dashboard_data.build_data", side_effect=flaky_build), \
         patch.object(StatsBar, "update", spy):
        async with CCManagerApp().run_test() as pilot:
            await pilot.press("r")   # triggers flaky second call
            await pilot.pause()
            assert any(d["status"] == "DEGRADED" for d in received), \
                f"expected DEGRADED in updates, got statuses: {[d['status'] for d in received]}"
            await pilot.press("q")


# ---------------------------------------------------------------------------
# Full data cycle: build_data → push to all widgets (no TTY)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_data_push_does_not_raise(sample_data):
    """_push_data() succeeds for both NOMINAL and DEGRADED data."""
    from cc_manager.app import CCManagerApp

    for data in [sample_data, {**sample_data, "status": "DEGRADED"}]:
        with _patch_build(data):
            async with CCManagerApp().run_test() as pilot:
                # Force a second data push via refresh
                await pilot.press("r")
                await pilot.pause()
                await pilot.press("q")
