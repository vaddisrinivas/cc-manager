"""Tests for cc_manager.commands.config"""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture(autouse=True)
def reset_ctx():
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None
    yield
    ctx_mod._ctx = None


@pytest.fixture
def patched_env(tmp_path, monkeypatch):
    manager_dir = tmp_path / ".cc-manager"
    manager_dir.mkdir()
    config_path = manager_dir / "cc-manager.toml"
    config_path.write_text('', encoding="utf-8")
    import cc_manager.context as ctx_mod
    monkeypatch.setattr(ctx_mod, "CONFIG_PATH", config_path)
    return {"config_path": config_path, "manager_dir": manager_dir}


def test_config_get(patched_env):
    ctx = MagicMock()
    ctx.config = {"backup_on_change": True}
    with patch("cc_manager.commands.config.get_ctx", return_value=ctx):
        with patch("cc_manager.commands.config.dot_get", return_value=True):
            from typer.testing import CliRunner
            from typer import Typer
            from cc_manager.commands.config import config_get_cmd
            app = Typer()
            app.command()(config_get_cmd)
            result = CliRunner().invoke(app, ["backup_on_change"])
    assert result.exit_code == 0
    assert "backup_on_change" in result.output


def test_config_set(patched_env):
    ctx = MagicMock()
    ctx.config = {}
    with patch("cc_manager.commands.config.get_ctx", return_value=ctx):
        with patch("cc_manager.commands.config.dot_set", return_value={"log_level": "debug"}):
            with patch("cc_manager.commands.config.ctx_mod.CONFIG_PATH", patched_env["config_path"]):
                from typer.testing import CliRunner
                from typer import Typer
                from cc_manager.commands.config import config_set_cmd
                app = Typer()
                app.command()(config_set_cmd)
                result = CliRunner().invoke(app, ["log_level", "debug"])
    assert result.exit_code == 0
    assert "Set" in result.output or "log_level" in result.output


def test_config_set_numeric(patched_env):
    ctx = MagicMock()
    ctx.config = {}
    with patch("cc_manager.commands.config.get_ctx", return_value=ctx):
        with patch("cc_manager.commands.config.dot_set", return_value={}):
            with patch("cc_manager.commands.config.ctx_mod.CONFIG_PATH", patched_env["config_path"]):
                from typer.testing import CliRunner
                from typer import Typer
                from cc_manager.commands.config import config_set_cmd
                app = Typer()
                app.command()(config_set_cmd)
                result = CliRunner().invoke(app, ["max_cost", "5"])
    assert result.exit_code == 0


def test_config_reset_requires_confirm(patched_env):
    from typer.testing import CliRunner
    from typer import Typer
    from cc_manager.commands.config import config_reset_cmd
    app = Typer()
    app.command()(config_reset_cmd)
    result = CliRunner().invoke(app)
    assert result.exit_code != 0 or "confirm" in result.output.lower()


def test_config_reset_with_confirm(patched_env):
    with patch("cc_manager.settings.backup_create"):
        from typer.testing import CliRunner
        from typer import Typer
        from cc_manager.commands.config import config_reset_cmd
        app = Typer()
        app.command()(config_reset_cmd)
        with patch("cc_manager.commands.config.ctx_mod.CONFIG_PATH", patched_env["config_path"]):
            result = CliRunner().invoke(app, ["--confirm"])
    assert result.exit_code == 0
    assert "reset" in result.output.lower()
