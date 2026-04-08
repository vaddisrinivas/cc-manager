"""Tests for cc_manager.commands.reset"""
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
    from cc_manager.commands.reset import reset_cmd
    app = Typer()
    app.command()(reset_cmd)
    return CliRunner().invoke(app, args or [])


def test_reset_config_requires_confirm():
    result = _invoke(["--config"])
    assert result.exit_code != 0
    assert "confirm" in result.output.lower()


def test_reset_all_requires_confirm():
    result = _invoke(["--all"])
    assert result.exit_code != 0
    assert "confirm" in result.output.lower()


def test_reset_config_with_confirm(tmp_path):
    config_path = tmp_path / "cc-manager.toml"
    config_path.write_text("", encoding="utf-8")
    ctx = MagicMock()
    with patch("cc_manager.context.get_ctx", return_value=ctx):
        with patch("cc_manager.settings.backup_create"):
            with patch("cc_manager.context.CONFIG_PATH", config_path):
                with patch("cc_manager.config.cfg") as mock_cfg:
                    mock_cfg.to_toml.return_value = "[manager]\nschema_version = 1\n"
                    result = _invoke(["--config", "--confirm"])
    assert result.exit_code == 0
    assert "reset" in result.output.lower()


def test_reset_noop_without_flags():
    ctx = MagicMock()
    with patch("cc_manager.context.get_ctx", return_value=ctx):
        result = _invoke([])
    assert result.exit_code == 0
