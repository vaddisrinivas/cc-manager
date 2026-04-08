"""Tests for cc_manager.commands.update"""
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture(autouse=True)
def reset_ctx():
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None
    yield
    ctx_mod._ctx = None


def _invoke(args=None):
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.update import update_cmd
    app = Typer()
    app.command()(update_cmd)
    return CliRunner().invoke(app, args or [])


REGISTRY = [
    {"name": "rtk", "install_methods": [{"type": "cargo", "command": "cargo install rtk"}]},
    {"name": "context7", "install_methods": [{"type": "mcp", "command": "npx context7"}]},
]


def test_update_all_tools():
    ctx = MagicMock()
    ctx.installed = {"tools": {"rtk": {"method": "cargo", "pinned": False}}}
    ctx.registry = REGISTRY
    with patch("cc_manager.commands.update.get_ctx", return_value=ctx):
        with patch("cc_manager.commands.update.run_cmd", return_value=(0, "ok")):
            result = _invoke()
    assert result.exit_code == 0
    assert "updated" in result.output or "rtk" in result.output


def test_update_skips_pinned():
    ctx = MagicMock()
    ctx.installed = {"tools": {"rtk": {"method": "cargo", "pinned": True}}}
    ctx.registry = REGISTRY
    with patch("cc_manager.commands.update.get_ctx", return_value=ctx):
        result = _invoke()
    assert result.exit_code == 0
    assert "Skipping pinned" in result.output


def test_update_specific_tool():
    ctx = MagicMock()
    ctx.installed = {"tools": {"rtk": {"method": "cargo", "pinned": False}}}
    ctx.registry = REGISTRY
    with patch("cc_manager.commands.update.get_ctx", return_value=ctx):
        with patch("cc_manager.commands.update.run_cmd", return_value=(0, "ok")) as mock_cmd:
            result = _invoke(["rtk"])
    assert result.exit_code == 0
    mock_cmd.assert_called_once()


def test_update_handles_failure():
    ctx = MagicMock()
    ctx.installed = {"tools": {"rtk": {"method": "cargo", "pinned": False}}}
    ctx.registry = REGISTRY
    with patch("cc_manager.commands.update.get_ctx", return_value=ctx):
        with patch("cc_manager.commands.update.run_cmd", return_value=(1, "error")):
            result = _invoke()
    assert result.exit_code == 0
    assert "failed" in result.output


def test_update_empty_tools():
    ctx = MagicMock()
    ctx.installed = {"tools": {}}
    ctx.registry = REGISTRY
    with patch("cc_manager.commands.update.get_ctx", return_value=ctx):
        result = _invoke()
    assert result.exit_code == 0
