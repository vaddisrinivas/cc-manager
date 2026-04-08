"""Tests for cc_manager.commands.why"""
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture(autouse=True)
def reset_ctx():
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None
    yield
    ctx_mod._ctx = None


def _invoke(name):
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.why import why_cmd
    app = Typer()
    app.command()(why_cmd)
    return CliRunner().invoke(app, [name])


def test_why_not_installed():
    ctx = MagicMock()
    ctx.installed = {"tools": {}}
    with patch("cc_manager.commands.why.get_ctx", return_value=ctx):
        result = _invoke("rtk")
    assert result.exit_code == 0
    assert "not installed" in result.output


def test_why_with_install_event():
    ctx = MagicMock()
    ctx.installed = {"tools": {"rtk": {"installed_at": "2026-01-01", "method": "cargo"}}}
    ctx.store.latest.return_value = {"ts": "2026-01-01T12:00:00", "event": "install", "tool": "rtk"}
    ctx.store.query.return_value = [{"ts": "2026-01-01T12:00:00", "event": "install", "tool": "rtk"}]
    with patch("cc_manager.commands.why.get_ctx", return_value=ctx):
        result = _invoke("rtk")
    assert result.exit_code == 0
    assert "ccm install rtk" in result.output or "2026-01-01" in result.output


def test_why_without_install_event():
    ctx = MagicMock()
    ctx.installed = {"tools": {"rtk": {"installed_at": "2026-01-01", "method": "cargo"}}}
    ctx.store.latest.return_value = None
    ctx.store.query.return_value = []
    with patch("cc_manager.commands.why.get_ctx", return_value=ctx):
        result = _invoke("rtk")
    assert result.exit_code == 0
    assert "2026-01-01" in result.output or "cargo" in result.output


def test_why_shows_method():
    ctx = MagicMock()
    ctx.installed = {"tools": {"context7": {"installed_at": "2026-02-01", "method": "mcp"}}}
    ctx.store.query.return_value = []
    with patch("cc_manager.commands.why.get_ctx", return_value=ctx):
        result = _invoke("context7")
    assert result.exit_code == 0
    assert "mcp" in result.output or "2026-02-01" in result.output
