"""Tests for cc_manager.commands.status"""
from unittest.mock import MagicMock, patch
import pytest

SESSION = {
    "ts": "2026-04-01T12:00:00+00:00",
    "event": "session_end",
    "input_tokens": 50000,
    "output_tokens": 10000,
    "cache_read": 5000,
    "cost_usd": 0.15,
    "duration_min": 30,
}


@pytest.fixture(autouse=True)
def reset_ctx():
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None
    yield
    ctx_mod._ctx = None


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.installed = {"tools": {}}
    ctx.settings = {}
    ctx.store.query.return_value = []   # get_week_stats uses store.query
    ctx.store.path.parent.exists.return_value = True
    return ctx


def _invoke(mock_ctx):
    with patch("cc_manager.commands.status.get_ctx", return_value=mock_ctx):
        with patch("cc_manager.commands.status.get_week_stats",
                   return_value=(mock_ctx.store.query.return_value, 0.0, 0, 0)):
            from cc_manager.commands.status import status_cmd
            from typer.testing import CliRunner
            from typer import Typer
            app = Typer()
            app.command()(status_cmd)
            return CliRunner().invoke(app)


def test_status_no_tools_no_session(mock_ctx):
    result = _invoke(mock_ctx)
    assert result.exit_code == 0


def test_status_with_tools(mock_ctx):
    mock_ctx.installed = {"tools": {
        "rtk": {"version": "1.0", "method": "cargo", "installed_at": "2026-01-01T00:00:00"}
    }}
    result = _invoke(mock_ctx)
    assert result.exit_code == 0
    assert "rtk" in result.output


def test_status_with_session_data(mock_ctx):
    mock_ctx.store.query.return_value = [SESSION]
    with patch("cc_manager.commands.status.get_ctx", return_value=mock_ctx):
        with patch("cc_manager.commands.status.get_week_stats",
                   return_value=([SESSION], 0.15, 1, 60000)):
            from cc_manager.commands.status import status_cmd
            from typer.testing import CliRunner
            from typer import Typer
            app = Typer()
            app.command()(status_cmd)
            result = CliRunner().invoke(app)
    assert result.exit_code == 0
    assert "0.1500" in result.output


def test_status_with_hooks(mock_ctx):
    mock_ctx.settings = {
        "hooks": {
            "Stop": [{"hooks": [{"command": "python ~/.cc-manager/hook.py Stop"}]}]
        }
    }
    result = _invoke(mock_ctx)
    assert result.exit_code == 0


def test_status_multiple_tools(mock_ctx):
    mock_ctx.installed = {"tools": {
        "rtk":      {"version": "1.0",    "method": "cargo", "installed_at": "2026-01-01T00:00:00"},
        "context7": {"version": "latest", "method": "mcp",   "installed_at": "2026-01-02T00:00:00"},
    }}
    result = _invoke(mock_ctx)
    assert result.exit_code == 0
    assert "rtk" in result.output
    assert "context7" in result.output
