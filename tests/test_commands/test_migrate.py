"""Tests for cc_manager.commands.migrate"""
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture(autouse=True)
def reset_ctx():
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None
    yield
    ctx_mod._ctx = None


def _invoke_check():
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.migrate import migrate_check_cmd
    app = Typer()
    app.command()(migrate_check_cmd)
    return CliRunner().invoke(app)


def _invoke_migrate():
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.migrate import migrate_cmd
    app = Typer()
    app.command()(migrate_cmd)
    return CliRunner().invoke(app)


def test_migrate_check_up_to_date():
    ctx = MagicMock()
    ctx.config = {"manager": {"schema_version": 1}}
    with patch("cc_manager.context.get_ctx", return_value=ctx):
        import cc_manager.context as ctx_mod
        ctx_mod._ctx = None
        result = _invoke_check()
    assert result.exit_code == 0
    assert "up to date" in result.output.lower() or "v1" in result.output


def test_migrate_check_needs_migration():
    ctx = MagicMock()
    ctx.config = {"manager": {"schema_version": 0}}
    with patch("cc_manager.context.get_ctx", return_value=ctx):
        import cc_manager.context as ctx_mod
        ctx_mod._ctx = None
        result = _invoke_check()
    assert result.exit_code == 0
    assert "Migration needed" in result.output or "schema_version" in result.output


def test_migrate_runs():
    with patch("cc_manager.commands.migrate.settings_mod.backup_create") as mock_backup:
        result = _invoke_migrate()
    assert result.exit_code == 0
    mock_backup.assert_called_once()
    assert "complete" in result.output.lower()


def test_migrate_creates_backup():
    with patch("cc_manager.commands.migrate.settings_mod.backup_create") as mock_backup:
        _invoke_migrate()
    assert mock_backup.call_count == 1
