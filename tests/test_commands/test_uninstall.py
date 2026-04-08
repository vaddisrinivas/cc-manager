"""Tests for cc_manager.commands.uninstall"""
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture(autouse=True)
def reset_ctx():
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None
    yield
    ctx_mod._ctx = None


def _invoke(args):
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.uninstall import uninstall_cmd
    app = Typer()
    app.command()(uninstall_cmd)
    return CliRunner().invoke(app, args)


def test_uninstall_not_installed():
    ctx = MagicMock()
    ctx.installed = {"tools": {}}
    with patch("cc_manager.commands.uninstall.get_ctx", return_value=ctx):
        result = _invoke(["nonexistent"])
    assert result.exit_code != 0
    assert "not installed" in result.output


def test_uninstall_mcp_tool():
    ctx = MagicMock()
    ctx.installed = {"tools": {"context7": {"method": "mcp", "version": "latest"}}}
    ctx.registry_map = {}
    with patch("cc_manager.commands.uninstall.get_ctx", return_value=ctx):
        with patch("cc_manager.commands.uninstall.settings_mod.remove_mcp") as mock_remove:
            result = _invoke(["context7"])
    assert result.exit_code == 0
    mock_remove.assert_called_once_with("context7")
    assert "uninstalled" in result.output


def test_uninstall_plugin_tool():
    ctx = MagicMock()
    ctx.installed = {"tools": {"cc-retrospect": {"method": "plugin", "version": "latest"}}}
    ctx.registry_map = {}
    with patch("cc_manager.commands.uninstall.get_ctx", return_value=ctx):
        result = _invoke(["cc-retrospect"])
    assert result.exit_code == 0
    assert "claude plugin uninstall" in result.output


def test_uninstall_records_event():
    ctx = MagicMock()
    ctx.installed = {"tools": {"rtk": {"method": "cargo", "version": "1.0"}}}
    ctx.registry_map = {"rtk": {"remove_hint": "cargo uninstall rtk"}}
    with patch("cc_manager.commands.uninstall.get_ctx", return_value=ctx):
        result = _invoke(["rtk"])
    assert result.exit_code == 0
    ctx.store.append.assert_called_once_with("uninstall", tool="rtk")


def test_uninstall_removes_from_installed():
    ctx = MagicMock()
    ctx.installed = {"tools": {"rtk": {"method": "cargo"}}}
    ctx.registry_map = {}
    with patch("cc_manager.commands.uninstall.get_ctx", return_value=ctx):
        result = _invoke(["rtk"])
    ctx.remove_installed.assert_called_once_with("rtk")
