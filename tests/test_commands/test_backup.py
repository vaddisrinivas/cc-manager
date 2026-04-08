"""Tests for cc_manager.commands.backup"""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture(autouse=True)
def reset_ctx():
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None
    yield
    ctx_mod._ctx = None


def _invoke_create():
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.backup import backup_create_cmd
    app = Typer()
    app.command()(backup_create_cmd)
    return CliRunner().invoke(app)


def _invoke_list():
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.backup import backup_list_cmd
    app = Typer()
    app.command()(backup_list_cmd)
    return CliRunner().invoke(app)


def _invoke_restore(ts):
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.backup import backup_restore_cmd
    app = Typer()
    app.command()(backup_restore_cmd)
    return CliRunner().invoke(app, [ts])


def test_backup_create(tmp_path):
    fake_path = tmp_path / "backup.json"
    fake_path.write_text("{}", encoding="utf-8")
    with patch("cc_manager.commands.backup.settings_mod.backup_create", return_value=fake_path):
        result = _invoke_create()
    assert result.exit_code == 0
    assert "Snapshot created" in result.output or "backup" in result.output.lower()


def test_backup_list_empty():
    with patch("cc_manager.commands.backup.settings_mod.backup_list", return_value=[]):
        result = _invoke_list()
    assert result.exit_code == 0
    assert "No backups" in result.output


def test_backup_list_with_backups(tmp_path):
    b1 = tmp_path / "settings.2026-01-01.json"
    b1.write_text("{}", encoding="utf-8")
    b2 = tmp_path / "settings.2026-01-02.json"
    b2.write_text("{}", encoding="utf-8")
    with patch("cc_manager.commands.backup.settings_mod.backup_list", return_value=[b1, b2]):
        result = _invoke_list()
    assert result.exit_code == 0
    assert "settings.2026-01-01.json" in result.output


def test_backup_restore():
    with patch("cc_manager.commands.backup.settings_mod.backup_restore") as mock_restore:
        result = _invoke_restore("2026-01-01T12:00:00")
    assert result.exit_code == 0
    mock_restore.assert_called_once_with("2026-01-01T12:00:00")
    assert "Restored" in result.output
