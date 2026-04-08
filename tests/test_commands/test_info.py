"""Tests for cc_manager.commands.info"""
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture(autouse=True)
def reset_ctx():
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None
    yield
    ctx_mod._ctx = None


REGISTRY = [
    {"name": "rtk", "description": "Token filter", "category": "productivity", "tier": "core",
     "repo": "https://github.com/example/rtk",
     "install_methods": [{"type": "cargo", "command": "cargo install rtk"}]},
]


def _invoke(name):
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.info import info_cmd
    app = Typer()
    app.command()(info_cmd)
    return CliRunner().invoke(app, [name])


def test_info_found():
    ctx = MagicMock()
    ctx.registry = REGISTRY
    ctx.installed = {"tools": {}}
    with patch("cc_manager.commands.info.get_ctx", return_value=ctx):
        result = _invoke("rtk")
    assert result.exit_code == 0
    assert "rtk" in result.output
    assert "Token filter" in result.output


def test_info_not_found():
    ctx = MagicMock()
    ctx.registry = REGISTRY
    ctx.installed = {"tools": {}}
    with patch("cc_manager.commands.info.get_ctx", return_value=ctx):
        result = _invoke("nonexistent")
    assert result.exit_code != 0
    assert "not found" in result.output


def test_info_shows_install_methods():
    ctx = MagicMock()
    ctx.registry = REGISTRY
    ctx.installed = {"tools": {}}
    with patch("cc_manager.commands.info.get_ctx", return_value=ctx):
        result = _invoke("rtk")
    assert "cargo" in result.output


def test_info_shows_installed_status():
    ctx = MagicMock()
    ctx.registry = REGISTRY
    ctx.installed = {"tools": {"rtk": {"version": "1.5", "method": "cargo"}}}
    with patch("cc_manager.commands.info.get_ctx", return_value=ctx):
        result = _invoke("rtk")
    assert result.exit_code == 0
    assert "Installed" in result.output or "1.5" in result.output


def test_info_shows_repo():
    ctx = MagicMock()
    ctx.registry = REGISTRY
    ctx.installed = {"tools": {}}
    with patch("cc_manager.commands.info.get_ctx", return_value=ctx):
        result = _invoke("rtk")
    assert "github.com" in result.output
