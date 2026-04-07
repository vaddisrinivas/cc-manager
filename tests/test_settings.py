"""Tests for cc_manager.settings"""
import json
from pathlib import Path

import pytest


@pytest.fixture
def settings_dir(tmp_path, monkeypatch):
    """Patch CLAUDE_DIR and MANAGER_DIR to tmp_path."""
    claude_dir = tmp_path / ".claude"
    manager_dir = tmp_path / ".cc-manager"
    claude_dir.mkdir()
    manager_dir.mkdir()
    (manager_dir / "backups").mkdir()

    import cc_manager.settings as smod
    monkeypatch.setattr(smod, "SETTINGS_PATH", claude_dir / "settings.json")
    monkeypatch.setattr(smod, "LOCK_PATH", manager_dir / ".settings.lock")
    monkeypatch.setattr(smod, "BACKUPS_DIR", manager_dir / "backups")
    return {"claude_dir": claude_dir, "manager_dir": manager_dir}


def write_settings(settings_dir, data):
    path = settings_dir["claude_dir"] / "settings.json"
    path.write_text(json.dumps(data))
    return path


def test_read_empty_returns_empty_dict(settings_dir):
    import cc_manager.settings as smod
    result = smod.read()
    assert result == {}


def test_read_existing_settings(settings_dir):
    write_settings(settings_dir, {"hooks": {}, "mcpServers": {}})
    import cc_manager.settings as smod
    result = smod.read()
    assert "hooks" in result


def test_write_creates_file(settings_dir):
    import cc_manager.settings as smod
    smod.write({"key": "value"}, backup=False)
    path = settings_dir["claude_dir"] / "settings.json"
    data = json.loads(path.read_text())
    assert data["key"] == "value"


def test_write_with_backup(settings_dir):
    write_settings(settings_dir, {"original": True})
    import cc_manager.settings as smod
    smod.write({"new": True}, backup=True)
    backups = smod.backup_list()
    assert len(backups) >= 1


def test_backup_create(settings_dir):
    write_settings(settings_dir, {"data": 42})
    import cc_manager.settings as smod
    bpath = smod.backup_create()
    assert bpath.exists()
    data = json.loads(bpath.read_text())
    assert data["data"] == 42


def test_backup_list(settings_dir):
    write_settings(settings_dir, {"a": 1})
    import cc_manager.settings as smod
    smod.backup_create()
    smod.backup_create()
    backups = smod.backup_list()
    assert len(backups) >= 2
    assert all(isinstance(p, Path) for p in backups)


def test_backup_restore(settings_dir):
    write_settings(settings_dir, {"version": 1})
    import cc_manager.settings as smod
    bpath = smod.backup_create()
    # Change settings
    smod.write({"version": 2}, backup=False)
    assert smod.read()["version"] == 2
    # Restore using timestamp part of filename
    ts = bpath.name.replace("settings.json.", "")
    smod.backup_restore(ts)
    assert smod.read()["version"] == 1


def test_merge_hooks(settings_dir):
    write_settings(settings_dir, {})
    import cc_manager.settings as smod
    smod.merge_hooks({
        "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "python3 ~/.cc-manager/hook.py Stop"}]}]
    })
    data = smod.read()
    assert "hooks" in data
    assert "Stop" in data["hooks"]


def test_merge_hooks_preserves_existing(settings_dir):
    write_settings(settings_dir, {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "user_hook"}]}]}})
    import cc_manager.settings as smod
    smod.merge_hooks({
        "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "python3 ~/.cc-manager/hook.py Stop"}]}]
    })
    data = smod.read()
    assert "PreToolUse" in data["hooks"]
    assert "Stop" in data["hooks"]


def test_remove_hooks(settings_dir):
    write_settings(settings_dir, {
        "hooks": {
            "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "python3 ~/.cc-manager/hook.py Stop"}]}],
            "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "user_hook"}]}]
        }
    })
    import cc_manager.settings as smod
    smod.remove_hooks()
    data = smod.read()
    assert "Stop" not in data.get("hooks", {})
    assert "PreToolUse" in data.get("hooks", {})


def test_merge_mcp(settings_dir):
    write_settings(settings_dir, {})
    import cc_manager.settings as smod
    smod.merge_mcp("context7", {"command": "npx", "args": ["-y", "@context7/mcp"]})
    data = smod.read()
    assert "mcpServers" in data
    assert "context7" in data["mcpServers"]
    assert data["mcpServers"]["context7"]["command"] == "npx"


def test_merge_mcp_preserves_existing(settings_dir):
    write_settings(settings_dir, {"mcpServers": {"existing": {"command": "cmd"}}})
    import cc_manager.settings as smod
    smod.merge_mcp("new_server", {"command": "npx"})
    data = smod.read()
    assert "existing" in data["mcpServers"]
    assert "new_server" in data["mcpServers"]


def test_remove_mcp(settings_dir):
    write_settings(settings_dir, {"mcpServers": {"context7": {"command": "npx"}, "other": {"command": "x"}}})
    import cc_manager.settings as smod
    smod.remove_mcp("context7")
    data = smod.read()
    assert "context7" not in data.get("mcpServers", {})
    assert "other" in data.get("mcpServers", {})


def test_remove_mcp_nonexistent(settings_dir):
    write_settings(settings_dir, {})
    import cc_manager.settings as smod
    # Should not raise
    smod.remove_mcp("nonexistent")
