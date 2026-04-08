"""Tests for cc_manager.commands.audit"""
from unittest.mock import MagicMock, patch
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
    from cc_manager.commands.audit import audit_cmd
    app = Typer()
    app.command()(audit_cmd)
    return CliRunner().invoke(app)


def test_audit_empty_settings():
    with patch("cc_manager.commands.audit.settings_mod.read", return_value={}):
        result = _invoke()
    assert result.exit_code == 0


def test_audit_shows_cc_manager_hooks():
    settings = {
        "hooks": {
            "Stop": [{"hooks": [{"command": "python ~/.cc-manager/hook.py Stop"}]}]
        }
    }
    with patch("cc_manager.commands.audit.settings_mod.read", return_value=settings):
        result = _invoke()
    assert result.exit_code == 0
    assert "cc-manager" in result.output


def test_audit_shows_mcp_servers():
    settings = {
        "mcpServers": {"context7": {"command": "npx", "args": ["context7"]}}
    }
    with patch("cc_manager.commands.audit.settings_mod.read", return_value=settings):
        result = _invoke()
    assert result.exit_code == 0
    assert "context7" in result.output
    assert "mcp" in result.output


def test_audit_shows_plugins():
    settings = {
        "enabledPlugins": ["cc-retrospect", "cc-budget"]
    }
    with patch("cc_manager.commands.audit.settings_mod.read", return_value=settings):
        result = _invoke()
    assert result.exit_code == 0
    assert "cc-retrospect" in result.output


def test_audit_user_hooks():
    settings = {
        "hooks": {
            "PostToolUse": [{"hooks": [{"command": "my-custom-script.sh"}]}]
        }
    }
    with patch("cc_manager.commands.audit.settings_mod.read", return_value=settings):
        result = _invoke()
    assert result.exit_code == 0
    assert "user" in result.output
