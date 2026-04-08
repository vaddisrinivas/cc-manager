"""Tests for cc_manager.commands.recommend"""
from unittest.mock import MagicMock, patch
import pytest


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
    return ctx


def _invoke(fn):
    from typer.testing import CliRunner
    from typer import Typer
    app = Typer()
    app.command()(fn)
    return CliRunner().invoke(app)


def test_recommend_no_sessions(mock_ctx):
    with patch("cc_manager.commands.recommend.get_ctx", return_value=mock_ctx):
        with patch("cc_manager.commands.analyze.compute_stats", return_value={"sessions": 0}):
            from cc_manager.commands.recommend import recommend_cmd
            result = _invoke(recommend_cmd)
    assert result.exit_code == 0
    assert "ALL CLEAR" in result.output or "great" in result.output.lower()


def test_recommend_rtk_for_high_tokens(mock_ctx):
    stats = {"sessions": 3, "avg_tokens_per_session": 600_000, "compaction_count": 0,
             "model_breakdown": {}, "total_cost_usd": 0.5, "total_output_tokens": 0}
    with patch("cc_manager.commands.recommend.get_ctx", return_value=mock_ctx):
        with patch("cc_manager.commands.analyze.compute_stats", return_value=stats):
            from cc_manager.commands.recommend import get_recommendations
            recs = get_recommendations(mock_ctx)
    assert any(r["tool"] == "rtk" for r in recs)


def test_recommend_cc_sentinel_for_high_cost(mock_ctx):
    stats = {"sessions": 5, "avg_tokens_per_session": 10_000, "compaction_count": 0,
             "model_breakdown": {}, "total_cost_usd": 1.5, "total_output_tokens": 50_000}
    with patch("cc_manager.commands.recommend.get_ctx", return_value=mock_ctx):
        with patch("cc_manager.commands.analyze.compute_stats", return_value=stats):
            from cc_manager.commands.recommend import get_recommendations
            recs = get_recommendations(mock_ctx)
    assert any(r["tool"] == "cc-sentinel" for r in recs)


def test_recommend_context7_no_mcp(mock_ctx):
    mock_ctx.settings = {}
    stats = {"sessions": 2, "avg_tokens_per_session": 10_000, "compaction_count": 0,
             "model_breakdown": {}, "total_cost_usd": 0.1, "total_output_tokens": 10_000}
    with patch("cc_manager.commands.recommend.get_ctx", return_value=mock_ctx):
        with patch("cc_manager.commands.analyze.compute_stats", return_value=stats):
            from cc_manager.commands.recommend import get_recommendations
            recs = get_recommendations(mock_ctx)
    assert any(r["tool"] == "context7" for r in recs)


def test_recommend_no_recs_when_already_installed(mock_ctx):
    mock_ctx.installed = {"tools": {"rtk": {}, "cc-sentinel": {}, "context7": {}, "caveman": {}, "cc-retrospect": {}, "cc-budget": {}}}
    mock_ctx.settings = {"mcpServers": {"context7": {}}}
    stats = {"sessions": 10, "avg_tokens_per_session": 700_000, "compaction_count": 5,
             "model_breakdown": {"claude-opus": 10}, "total_cost_usd": 5.0, "total_output_tokens": 3_000_000}
    with patch("cc_manager.commands.recommend.get_ctx", return_value=mock_ctx):
        with patch("cc_manager.commands.analyze.compute_stats", return_value=stats):
            from cc_manager.commands.recommend import get_recommendations
            recs = get_recommendations(mock_ctx)
    tool_recs = [r["tool"] for r in recs if r["tool"] is not None]
    assert "rtk" not in tool_recs


def test_recommend_cmd_output(mock_ctx):
    stats = {"sessions": 1, "avg_tokens_per_session": 10_000, "compaction_count": 0,
             "model_breakdown": {}, "total_cost_usd": 0.1, "total_output_tokens": 10_000}
    with patch("cc_manager.commands.recommend.get_ctx", return_value=mock_ctx):
        with patch("cc_manager.commands.analyze.compute_stats", return_value=stats):
            from cc_manager.commands.recommend import recommend_cmd
            result = _invoke(recommend_cmd)
    assert result.exit_code == 0
