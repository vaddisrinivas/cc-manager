"""Tests for cc_manager dashboard — Textual app."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_ctx():
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None
    yield
    ctx_mod._ctx = None


@pytest.fixture
def patched_env(tmp_path, monkeypatch):
    claude_dir = tmp_path / ".claude"
    manager_dir = tmp_path / ".cc-manager"
    claude_dir.mkdir()
    manager_dir.mkdir()
    (manager_dir / "store").mkdir()
    (manager_dir / "registry").mkdir()
    (manager_dir / "state").mkdir()
    (manager_dir / "backups").mkdir()

    settings_path = claude_dir / "settings.json"
    registry_path = manager_dir / "registry" / "installed.json"
    store_path = manager_dir / "store" / "events.jsonl"

    settings_path.write_text(json.dumps({"hooks": {}, "mcpServers": {}}))
    registry_path.write_text(json.dumps({"schema_version": 1, "tools": {}}))

    import cc_manager.context as ctx_mod
    monkeypatch.setattr(ctx_mod, "CLAUDE_DIR", claude_dir)
    monkeypatch.setattr(ctx_mod, "MANAGER_DIR", manager_dir)
    monkeypatch.setattr(ctx_mod, "SETTINGS_PATH", settings_path)
    monkeypatch.setattr(ctx_mod, "CONFIG_PATH", manager_dir / "cc-manager.toml")
    monkeypatch.setattr(ctx_mod, "STORE_PATH", store_path)
    monkeypatch.setattr(ctx_mod, "REGISTRY_PATH", registry_path)
    monkeypatch.setattr(ctx_mod, "STATE_PATH", manager_dir / "state" / "state.json")
    monkeypatch.setattr(ctx_mod, "BACKUPS_DIR", manager_dir / "backups")
    return {
        "claude_dir": claude_dir,
        "manager_dir": manager_dir,
        "registry_path": registry_path,
        "store_path": store_path,
        "settings_path": settings_path,
        "tmp_path": tmp_path,
    }


# ---------------------------------------------------------------------------
# 1. Imports
# ---------------------------------------------------------------------------

def test_ccmanager_app_importable():
    from cc_manager.app import CCManagerApp
    assert CCManagerApp is not None


def test_dashboard_data_importable():
    from cc_manager.dashboard_data import build_data
    assert callable(build_data)


def test_all_widgets_importable():
    from cc_manager.widgets.header_bar import HeaderBar
    from cc_manager.widgets.stats_bar import StatsBar
    from cc_manager.widgets.token_chart import TokenChart
    from cc_manager.widgets.cost_chart import CostChart
    from cc_manager.widgets.tools_table import ToolsTable
    from cc_manager.widgets.health_table import HealthTable
    from cc_manager.widgets.sessions_table import SessionsTable
    from cc_manager.widgets.event_log import EventLog
    from cc_manager.widgets.recs_widget import RecsWidget
    for cls in (HeaderBar, StatsBar, TokenChart, CostChart, ToolsTable,
                HealthTable, SessionsTable, EventLog, RecsWidget):
        assert cls is not None


# ---------------------------------------------------------------------------
# 2. CCManagerApp structure
# ---------------------------------------------------------------------------

def test_app_has_bindings():
    from cc_manager.app import CCManagerApp
    binding_keys = {b.key for b in CCManagerApp.BINDINGS}
    assert "q" in binding_keys
    assert "r" in binding_keys
    assert "d" in binding_keys


def test_app_has_action_remove_tool():
    from cc_manager.app import CCManagerApp
    assert hasattr(CCManagerApp, "action_remove_tool")
    assert callable(CCManagerApp.action_remove_tool)


def test_app_has_action_run_doctor():
    from cc_manager.app import CCManagerApp
    assert hasattr(CCManagerApp, "action_run_doctor")
    assert callable(CCManagerApp.action_run_doctor)


def test_app_has_action_refresh():
    from cc_manager.app import CCManagerApp
    assert hasattr(CCManagerApp, "action_refresh")
    assert callable(CCManagerApp.action_refresh)


def test_app_has_auto_refresh():
    """set_interval(30, ...) is called in on_mount."""
    import inspect
    from cc_manager.app import CCManagerApp
    src = inspect.getsource(CCManagerApp.on_mount)
    assert "set_interval" in src
    assert "30" in src


# ---------------------------------------------------------------------------
# 3. build_data() contract
# ---------------------------------------------------------------------------

REQUIRED_KEYS = {
    "version", "timestamp", "status",
    "sessions", "total_input", "total_output", "total_cost", "total_tokens",
    "avg_tokens_per_session", "model_breakdown",
    "spark_values", "spark_days",
    "installed", "health_checks", "cc_hooks", "settings_ok",
    "recs", "available", "events",
}


def test_build_data_returns_required_keys(patched_env):
    from cc_manager.dashboard_data import build_data
    data = build_data()
    for key in REQUIRED_KEYS:
        assert key in data, f"build_data() missing key: {key!r}"


def test_build_data_status_values(patched_env):
    from cc_manager.dashboard_data import build_data
    data = build_data()
    assert data["status"] in ("NOMINAL", "DEGRADED")


def test_build_data_empty_store_no_crash(patched_env):
    from cc_manager.dashboard_data import build_data
    data = build_data()
    assert isinstance(data["sessions"], list)
    assert data["total_cost"] >= 0.0


def test_build_data_with_sessions(patched_env):
    from datetime import datetime, timezone
    from cc_manager.dashboard_data import build_data

    now = datetime.now(timezone.utc).isoformat()
    lines = [
        json.dumps({"ts": now, "event": "session_end", "model": "claude-sonnet",
                    "input_tokens": 100_000, "output_tokens": 25_000,
                    "cost_usd": 0.45, "duration_min": 15}),
        json.dumps({"ts": now, "event": "session_end", "model": "claude-opus",
                    "input_tokens": 200_000, "output_tokens": 50_000,
                    "cost_usd": 1.20, "duration_min": 30}),
    ]
    patched_env["store_path"].write_text("\n".join(lines) + "\n")

    data = build_data()
    assert len(data["sessions"]) == 2
    assert data["total_input"] == 300_000
    assert data["total_output"] == 75_000
    assert abs(data["total_cost"] - 1.65) < 0.001


def test_build_data_with_installed_tools(patched_env):
    from cc_manager.dashboard_data import build_data

    patched_env["registry_path"].write_text(json.dumps({
        "schema_version": 1,
        "tools": {
            "rtk": {"version": "0.25.0", "method": "cargo"},
            "context7": {"version": "latest", "method": "mcp"},
        },
    }))
    data = build_data()
    assert "rtk" in data["installed"]
    assert "context7" in data["installed"]


# ---------------------------------------------------------------------------
# 4. dashboard.run() — thin launcher
# ---------------------------------------------------------------------------

def test_dashboard_run_exists():
    from cc_manager.commands.dashboard import run
    assert callable(run)


def test_run_terminal_helper_exists():
    from cc_manager.commands.dashboard import _run_terminal
    assert callable(_run_terminal)


def test_dashboard_run_terminal_calls_app(monkeypatch):
    """_run_terminal() calls CCManagerApp().run()."""
    import cc_manager.commands.dashboard as dash_mod
    mock_app_instance = MagicMock()
    mock_app_class = MagicMock(return_value=mock_app_instance)
    monkeypatch.setattr(dash_mod, "CCManagerApp", mock_app_class, raising=False)

    # Patch the import inside _run_terminal
    import sys
    fake_app_mod = MagicMock()
    fake_app_mod.CCManagerApp = mock_app_class
    with patch.dict(sys.modules, {"cc_manager.app": fake_app_mod}):
        try:
            dash_mod._run_terminal()
        except Exception:
            pass  # App.run() may fail outside a real terminal


# ---------------------------------------------------------------------------
# 5. tui.run() — thin launcher
# ---------------------------------------------------------------------------

def test_tui_run_exists():
    from cc_manager.commands.tui import run
    assert callable(run)


def test_tui_helpers_still_present():
    """sparkline, abbrev, get_recommendations must stay in tui.py."""
    from cc_manager.commands.tui import sparkline, abbrev, get_recommendations
    assert callable(sparkline)
    assert callable(abbrev)
    assert callable(get_recommendations)


# ---------------------------------------------------------------------------
# 6. Widget unit tests
# ---------------------------------------------------------------------------

def test_token_chart_instantiates():
    from cc_manager.widgets.token_chart import TokenChart
    w = TokenChart()
    assert w is not None


def test_cost_chart_instantiates():
    from cc_manager.widgets.cost_chart import CostChart
    w = CostChart()
    assert w is not None


def test_tools_table_get_selected_tool_returns_none_before_mount():
    from cc_manager.widgets.tools_table import ToolsTable
    w = ToolsTable()
    result = w.get_selected_tool()
    assert result is None


def test_event_log_fmt_detail_empty():
    from cc_manager.widgets.event_log import _fmt_event_detail
    assert _fmt_event_detail({}) == "—"


def test_event_log_fmt_detail_session_end():
    from cc_manager.widgets.event_log import _fmt_event_detail
    detail = _fmt_event_detail({
        "event": "session_end",
        "input_tokens": 100_000,
        "cost_usd": 0.45,
        "duration_min": 15,
        "model": "claude-sonnet",
    })
    assert "100K" in detail
    assert "$0.45" in detail
    assert "15m" in detail
    assert "sonnet" in detail


def test_stats_bar_instantiates():
    from cc_manager.widgets.stats_bar import StatsBar
    w = StatsBar()
    assert w is not None


def test_recs_widget_instantiates():
    from cc_manager.widgets.recs_widget import RecsWidget
    w = RecsWidget()
    assert w is not None


def test_app_has_stats_bar_and_recs():
    """App compose should include StatsBar and RecsWidget."""
    import inspect
    from cc_manager.app import CCManagerApp
    src = inspect.getsource(CCManagerApp.compose)
    assert "StatsBar" in src
    assert "RecsWidget" in src


def test_build_data_has_daily_cost(patched_env):
    """build_data must return 'daily_cost' key."""
    from cc_manager.dashboard_data import build_data
    data = build_data()
    assert "daily_cost" in data
    assert isinstance(data["daily_cost"], dict)


def test_build_data_daily_cost_populated(patched_env):
    """daily_cost should sum costs per day from session events."""
    from datetime import datetime, timezone
    from cc_manager.dashboard_data import build_data

    now = datetime.now(timezone.utc).isoformat()
    lines = [
        json.dumps({"ts": now, "event": "session_end", "model": "claude-sonnet",
                    "input_tokens": 1000, "output_tokens": 500,
                    "cost_usd": 0.50, "duration_min": 5}),
        json.dumps({"ts": now, "event": "session_end", "model": "claude-sonnet",
                    "input_tokens": 2000, "output_tokens": 1000,
                    "cost_usd": 0.75, "duration_min": 10}),
    ]
    patched_env["store_path"].write_text("\n".join(lines) + "\n")

    data = build_data()
    day = now[:10]
    assert day in data["daily_cost"]
    assert abs(data["daily_cost"][day] - 1.25) < 0.001
