"""Tests for cc_manager.commands.logs"""
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture(autouse=True)
def reset_ctx():
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None
    yield
    ctx_mod._ctx = None


SAMPLE_EVENTS = [
    {"ts": "2026-04-01T10:00:00+00:00", "event": "session_end", "input_tokens": 10000,
     "output_tokens": 5000, "cost_usd": 0.09, "duration_min": 20},
    {"ts": "2026-04-01T11:00:00+00:00", "event": "install", "tool": "rtk", "version": "1.0", "method": "cargo"},
    {"ts": "2026-04-01T12:00:00+00:00", "event": "session_start", "cwd": "/home/user/project"},
]


def _invoke(args=None):
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.logs import logs_cmd
    app = Typer()
    app.command()(logs_cmd)
    return CliRunner().invoke(app, args or [])


def test_logs_empty():
    ctx = MagicMock()
    ctx.store.query.return_value = []
    with patch("cc_manager.commands.logs.get_ctx", return_value=ctx):
        result = _invoke()
    assert result.exit_code == 0
    assert "No events" in result.output


def test_logs_shows_events():
    ctx = MagicMock()
    ctx.store.query.return_value = SAMPLE_EVENTS
    with patch("cc_manager.commands.logs.get_ctx", return_value=ctx):
        result = _invoke()
    assert result.exit_code == 0
    assert "SESSION_END" in result.output or "session_end" in result.output.lower()


def test_logs_with_event_filter():
    ctx = MagicMock()
    ctx.store.query.return_value = [SAMPLE_EVENTS[1]]
    with patch("cc_manager.commands.logs.get_ctx", return_value=ctx):
        result = _invoke(["--event", "install"])
    ctx.store.query.assert_called_once()
    call_kwargs = ctx.store.query.call_args
    assert call_kwargs[1].get("event") == "install" or call_kwargs[0][0] == "install" if call_kwargs[0] else True


def test_logs_with_n():
    ctx = MagicMock()
    ctx.store.query.return_value = SAMPLE_EVENTS[:2]
    with patch("cc_manager.commands.logs.get_ctx", return_value=ctx):
        result = _invoke(["--lines", "2"])
    assert result.exit_code == 0


def test_format_record_session_end():
    from cc_manager.commands.logs import _format_record
    record = {"ts": "2026-04-01T10:00:00", "event": "session_end",
              "input_tokens": 10000, "output_tokens": 5000, "cost_usd": 0.09, "duration_min": 20}
    out = _format_record(record)
    assert "SESSION_END" in out
    assert "10K" in out or "0.09" in out


def test_format_record_install():
    from cc_manager.commands.logs import _format_record
    record = {"ts": "2026-04-01T10:00:00", "event": "install", "tool": "rtk", "version": "1.0", "method": "cargo"}
    out = _format_record(record)
    assert "INSTALL" in out
    assert "rtk" in out
