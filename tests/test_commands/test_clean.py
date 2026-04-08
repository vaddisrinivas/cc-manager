"""Tests for cc_manager.commands.clean"""
from pathlib import Path
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
    from cc_manager.commands.clean import clean_cmd
    app = Typer()
    app.command()(clean_cmd)
    return CliRunner().invoke(app, args)


def test_clean_no_flags():
    ctx = MagicMock()
    with patch("cc_manager.commands.clean.get_ctx", return_value=ctx):
        result = _invoke([])
    # No flags = no action, no crash
    assert result.exit_code == 0


def test_clean_backups_dry_run(tmp_path):
    backups = [tmp_path / f"settings.{i}.json" for i in range(8)]
    for b in backups:
        b.write_text("{}", encoding="utf-8")

    ctx = MagicMock()
    with patch("cc_manager.commands.clean.get_ctx", return_value=ctx):
        with patch("cc_manager.settings.backup_list", return_value=backups):
            result = _invoke(["--backups", "--dry-run", "--keep-last", "5"])
    assert result.exit_code == 0
    assert "Would delete" in result.output


def test_clean_backups_keeps_last_n(tmp_path):
    backups = [tmp_path / f"settings.{i}.json" for i in range(8)]
    for b in backups:
        b.write_text("{}", encoding="utf-8")

    ctx = MagicMock()
    with patch("cc_manager.commands.clean.get_ctx", return_value=ctx):
        with patch("cc_manager.settings.backup_list", return_value=backups):
            result = _invoke(["--backups", "--keep-last", "5"])
    assert result.exit_code == 0
    assert "Removed 3" in result.output


def test_clean_sessions_dry_run(tmp_path):
    ctx = MagicMock()
    with patch("cc_manager.commands.clean.get_ctx", return_value=ctx):
        with patch("cc_manager.commands.clean.Path.home", return_value=tmp_path):
            result = _invoke(["--sessions", "--dry-run"])
    assert result.exit_code == 0


def test_clean_parse_duration():
    from cc_manager.context import parse_duration
    assert parse_duration("7d").days == 7
    assert parse_duration("24h").total_seconds() == 86400
    with pytest.raises(ValueError):
        parse_duration("bad")
