"""Tests for cc_manager.commands.diff"""
from unittest.mock import MagicMock, patch
import json
import pytest


@pytest.fixture(autouse=True)
def reset_ctx():
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None
    yield
    ctx_mod._ctx = None


def _invoke():
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.diff import diff_cmd
    app = Typer()
    app.command()(diff_cmd)
    return CliRunner().invoke(app)


def test_diff_no_backups():
    with patch("cc_manager.commands.diff.settings_mod.backup_list", return_value=[]):
        result = _invoke()
    assert result.exit_code == 0
    assert "No backups" in result.output


def test_diff_no_changes(tmp_path):
    settings = {"hooks": {}, "mcpServers": {}}
    backup = tmp_path / "settings.backup.json"
    backup.write_text(json.dumps(settings), encoding="utf-8")
    with patch("cc_manager.commands.diff.settings_mod.backup_list", return_value=[backup]):
        with patch("cc_manager.commands.diff.settings_mod.read", return_value=settings):
            result = _invoke()
    assert result.exit_code == 0
    assert "No changes" in result.output


def test_diff_shows_added(tmp_path):
    old = {"hooks": {}}
    new = {"hooks": {}, "mcpServers": {"context7": {}}}
    backup = tmp_path / "settings.backup.json"
    backup.write_text(json.dumps(old), encoding="utf-8")
    with patch("cc_manager.commands.diff.settings_mod.backup_list", return_value=[backup]):
        with patch("cc_manager.commands.diff.settings_mod.read", return_value=new):
            result = _invoke()
    assert result.exit_code == 0
    assert "+" in result.output or "added" in result.output.lower()


def test_diff_shows_removed(tmp_path):
    old = {"hooks": {}, "mcpServers": {"context7": {}}}
    new = {"hooks": {}}
    backup = tmp_path / "settings.backup.json"
    backup.write_text(json.dumps(old), encoding="utf-8")
    with patch("cc_manager.commands.diff.settings_mod.backup_list", return_value=[backup]):
        with patch("cc_manager.commands.diff.settings_mod.read", return_value=new):
            result = _invoke()
    assert result.exit_code == 0
    assert "-" in result.output or "removed" in result.output.lower()


def test_recursive_diff_logic():
    from cc_manager.commands.diff import _recursive_diff
    old = {"a": 1, "b": {"c": 2}}
    new = {"a": 1, "b": {"c": 3}, "d": 4}
    changes = _recursive_diff(old, new)
    kinds = {c[0] for c in changes}
    assert "changed" in kinds
    assert "added" in kinds
