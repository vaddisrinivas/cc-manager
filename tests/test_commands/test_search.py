"""Tests for cc_manager.commands.search"""
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture(autouse=True)
def reset_ctx():
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None
    yield
    ctx_mod._ctx = None


REGISTRY = [
    {"name": "rtk", "description": "Token filter for Claude Code", "category": "productivity",
     "tier": "core", "install_methods": [{"type": "cargo", "command": "cargo install rtk"}]},
    {"name": "context7", "description": "MCP for docs context", "category": "mcp-server",
     "tier": "recommended", "install_methods": [{"type": "mcp", "command": "npx context7"}]},
    {"name": "caveman", "description": "Reduces output tokens with skill", "category": "skill",
     "tier": "useful", "install_methods": []},
]


def _invoke(query):
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.search import search_cmd
    app = Typer()
    app.command()(search_cmd)
    return CliRunner().invoke(app, [query])


def test_search_by_name():
    ctx = MagicMock()
    ctx.registry = REGISTRY
    with patch("cc_manager.commands.search.get_ctx", return_value=ctx):
        result = _invoke("rtk")
    assert result.exit_code == 0
    assert "rtk" in result.output


def test_search_by_description():
    ctx = MagicMock()
    ctx.registry = REGISTRY
    with patch("cc_manager.commands.search.get_ctx", return_value=ctx):
        result = _invoke("token")
    assert result.exit_code == 0
    assert "rtk" in result.output


def test_search_by_category():
    ctx = MagicMock()
    ctx.registry = REGISTRY
    with patch("cc_manager.commands.search.get_ctx", return_value=ctx):
        result = _invoke("mcp-server")
    assert result.exit_code == 0
    assert "context7" in result.output


def test_search_no_results():
    ctx = MagicMock()
    ctx.registry = REGISTRY
    with patch("cc_manager.commands.search.get_ctx", return_value=ctx):
        result = _invoke("zzznomatchzzz")
    assert result.exit_code == 0
    assert "NO RESULTS" in result.output or "No tools" in result.output


def test_search_case_insensitive():
    ctx = MagicMock()
    ctx.registry = REGISTRY
    with patch("cc_manager.commands.search.get_ctx", return_value=ctx):
        result = _invoke("RTK")
    assert result.exit_code == 0
    assert "rtk" in result.output


def test_search_shows_all_results(monkeypatch):
    big_registry = [
        {"name": f"tool-{i}", "description": f"tool number {i}", "category": "test",
         "tier": "useful", "install_methods": []}
        for i in range(10)
    ]
    ctx = MagicMock()
    ctx.registry = big_registry
    with patch("cc_manager.commands.search.get_ctx", return_value=ctx):
        result = _invoke("tool")
    assert result.exit_code == 0
    assert "10 results" in result.output  # Shows all, not capped at 5
