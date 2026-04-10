"""Tests for cc_manager.settings."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cc_manager import settings


@pytest.fixture
def tmp_settings(tmp_path):
    """Redirect all settings paths to tmp_path."""
    s = tmp_path / "settings.json"
    lock = tmp_path / ".lock"
    backups = tmp_path / "backups"
    with patch.object(settings, "SETTINGS_PATH", s), \
         patch.object(settings, "LOCK_PATH", lock), \
         patch.object(settings, "BACKUPS_DIR", backups):
        yield s


def test_read_missing(tmp_settings):
    assert settings.read() == {}


def test_write_and_read(tmp_settings):
    settings.write({"foo": "bar"}, backup=False)
    assert settings.read() == {"foo": "bar"}


def test_write_creates_backup(tmp_settings):
    settings.write({"v": 1}, backup=False)
    settings.write({"v": 2}, backup=True)
    backups = settings.backup_list()
    assert len(backups) == 1
    content = json.loads(backups[0].read_text())
    assert content == {"v": 1}


def test_merge_hooks(tmp_settings):
    settings.write({"hooks": {"existing": []}}, backup=False)
    settings.merge_hooks({"SessionStart": [{"matcher": "", "hooks": []}]})
    data = settings.read()
    assert "existing" in data["hooks"]
    assert "SessionStart" in data["hooks"]


def test_merge_mcp(tmp_settings):
    settings.write({}, backup=False)
    settings.merge_mcp("test-server", {"command": "node", "args": ["server.js"]})
    data = settings.read()
    assert data["mcpServers"]["test-server"]["command"] == "node"


def test_remove_mcp(tmp_settings):
    settings.write({"mcpServers": {"a": {}, "b": {}}}, backup=False)
    settings.remove_mcp("a")
    data = settings.read()
    assert "a" not in data.get("mcpServers", {})
    assert "b" in data["mcpServers"]


def test_remove_hooks(tmp_settings):
    settings.write({
        "hooks": {
            "SessionStart": [
                {"matcher": "", "hooks": [
                    {"type": "command", "command": "/path/.cc-manager/hooks SessionStart"},
                    {"type": "command", "command": "/other/tool start"},
                ]}
            ]
        }
    }, backup=False)
    settings.remove_hooks()
    data = settings.read()
    hooks = data["hooks"]
    # The .cc-manager hook should be removed, /other/tool should remain
    assert len(hooks["SessionStart"][0]["hooks"]) == 1
    assert "/other/tool" in hooks["SessionStart"][0]["hooks"][0]["command"]


def test_read_corrupt_json(tmp_settings):
    tmp_settings.write_text("not json{{{")
    assert settings.read() == {}


def test_backup_list_empty(tmp_settings):
    assert settings.backup_list() == []
