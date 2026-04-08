"""Tests for cc_manager.commands.pin"""
import json
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture(autouse=True)
def reset_ctx():
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None
    yield
    ctx_mod._ctx = None


def _invoke_pin(name):
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.pin import pin_cmd
    app = Typer()
    app.command()(pin_cmd)
    return CliRunner().invoke(app, [name])


def _invoke_unpin(name):
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.pin import unpin_cmd
    app = Typer()
    app.command()(unpin_cmd)
    return CliRunner().invoke(app, [name])


def _invoke_list():
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.pin import pin_list_cmd
    app = Typer()
    app.command()(pin_list_cmd)
    return CliRunner().invoke(app)


def test_pin_not_installed():
    ctx = MagicMock()
    ctx.installed = {"tools": {}}
    with patch("cc_manager.commands.pin.get_ctx", return_value=ctx):
        result = _invoke_pin("rtk")
    assert result.exit_code != 0
    assert "not installed" in result.output


def test_pin_success(tmp_path):
    ctx = MagicMock()
    ctx.installed = {"tools": {"rtk": {"method": "cargo", "pinned": False}}}
    registry_path = tmp_path / "installed.json"
    with patch("cc_manager.commands.pin.get_ctx", return_value=ctx):
        with patch("cc_manager.commands.pin.ctx_mod.REGISTRY_PATH", registry_path):
            result = _invoke_pin("rtk")
    assert result.exit_code == 0
    assert "Pinned" in result.output
    assert ctx.installed["tools"]["rtk"]["pinned"] is True


def test_unpin_success(tmp_path):
    ctx = MagicMock()
    ctx.installed = {"tools": {"rtk": {"method": "cargo", "pinned": True}}}
    registry_path = tmp_path / "installed.json"
    with patch("cc_manager.commands.pin.get_ctx", return_value=ctx):
        with patch("cc_manager.commands.pin.ctx_mod.REGISTRY_PATH", registry_path):
            result = _invoke_unpin("rtk")
    assert result.exit_code == 0
    assert "Unpinned" in result.output
    assert ctx.installed["tools"]["rtk"]["pinned"] is False


def test_pin_list_empty():
    ctx = MagicMock()
    ctx.installed = {"tools": {"rtk": {"pinned": False}}}
    with patch("cc_manager.commands.pin.get_ctx", return_value=ctx):
        result = _invoke_list()
    assert result.exit_code == 0
    assert "No pinned" in result.output


def test_pin_list_shows_pinned():
    ctx = MagicMock()
    ctx.installed = {"tools": {"rtk": {"pinned": True}, "context7": {"pinned": False}}}
    with patch("cc_manager.commands.pin.get_ctx", return_value=ctx):
        result = _invoke_list()
    assert result.exit_code == 0
    assert "rtk" in result.output
    assert "context7" not in result.output
