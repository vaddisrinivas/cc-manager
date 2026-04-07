"""Tests for cc_manager.commands.install"""
import json
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
    claude_dir = tmp_path / ".claude"
    manager_dir = tmp_path / ".cc-manager"
    claude_dir.mkdir()
    manager_dir.mkdir()
    (manager_dir / "store").mkdir()
    (manager_dir / "registry").mkdir()
    (manager_dir / "state").mkdir()
    (manager_dir / "backups").mkdir()

    settings_path = claude_dir / "settings.json"
    registry_path = manager_dir / "registry" / "installed.json"
    store_path = manager_dir / "store" / "events.jsonl"

    import cc_manager.context as ctx_mod
    import cc_manager.settings as smod
    monkeypatch.setattr(ctx_mod, "CLAUDE_DIR", claude_dir)
    monkeypatch.setattr(ctx_mod, "MANAGER_DIR", manager_dir)
    monkeypatch.setattr(ctx_mod, "SETTINGS_PATH", settings_path)
    monkeypatch.setattr(ctx_mod, "CONFIG_PATH", manager_dir / "cc-manager.toml")
    monkeypatch.setattr(ctx_mod, "STORE_PATH", store_path)
    monkeypatch.setattr(ctx_mod, "REGISTRY_PATH", registry_path)
    monkeypatch.setattr(ctx_mod, "STATE_PATH", manager_dir / "state" / "state.json")
    monkeypatch.setattr(ctx_mod, "BACKUPS_DIR", manager_dir / "backups")
    monkeypatch.setattr(smod, "SETTINGS_PATH", settings_path)
    monkeypatch.setattr(smod, "LOCK_PATH", manager_dir / ".settings.lock")
    monkeypatch.setattr(smod, "BACKUPS_DIR", manager_dir / "backups")

    return {
        "claude_dir": claude_dir,
        "manager_dir": manager_dir,
        "registry_path": registry_path,
        "store_path": store_path,
        "settings_path": settings_path,
    }


def get_installed(patched_env):
    path = patched_env["registry_path"]
    if not path.exists():
        return {"schema_version": 1, "tools": {}}
    return json.loads(path.read_text())


def test_install_cargo_tool(patched_env):
    from cc_manager.commands.install import install_tool
    with patch("cc_manager.commands.install.run_cmd", return_value=(0, "rtk 0.25.0")) as mock_run:
        install_tool("rtk", dry_run=False)
        # Should have called run_cmd with cargo install
        assert mock_run.called
        call_args = mock_run.call_args[0][0]
        assert "cargo" in call_args or "brew" in call_args or "install" in call_args

    installed = get_installed(patched_env)
    assert "rtk" in installed["tools"]


def test_install_mcp_tool(patched_env):
    from cc_manager.commands.install import install_tool
    import cc_manager.settings as smod
    install_tool("context7", dry_run=False)
    data = smod.read()
    # context7 is an MCP tool - should be added to mcpServers
    assert "mcpServers" in data
    assert "context7" in data["mcpServers"]


def test_install_already_installed_raises(patched_env):
    from cc_manager.commands.install import install_tool, AlreadyInstalledError
    # Pre-populate installed.json
    installed_data = {"schema_version": 1, "tools": {"rtk": {"version": "0.25.0", "method": "cargo"}}}
    patched_env["registry_path"].write_text(json.dumps(installed_data))

    with pytest.raises(AlreadyInstalledError):
        install_tool("rtk", dry_run=False)


def test_install_conflict_detection(patched_env):
    """Tools that conflict with each other should raise ConflictError."""
    from cc_manager.commands.install import install_tool, ConflictError
    import cc_manager.context as ctx_mod

    # Write fake_tool_b as already installed BEFORE creating ctx
    installed_data = {"schema_version": 1, "tools": {"fake_tool_b": {"version": "1.0.0", "method": "npm"}}}
    patched_env["registry_path"].write_text(json.dumps(installed_data))

    # Now get ctx (will load installed_data from file)
    ctx = ctx_mod.get_ctx()

    # Inject fake tools into registry
    fake_tool = {
        "name": "fake_tool_a",
        "description": "fake",
        "category": "test",
        "tier": "popular",
        "conflicts_with": ["fake_tool_b"],
        "install_methods": [{"type": "npm", "command": "npm install -g fake-tool-a", "binary": "fake-tool-a"}],
        "detect": {"type": "binary", "command": "fake-tool-a --version"},
    }
    fake_tool_b = {
        "name": "fake_tool_b",
        "description": "fake b",
        "category": "test",
        "tier": "popular",
        "conflicts_with": [],
        "install_methods": [{"type": "npm", "command": "npm install -g fake-tool-b", "binary": "fake-tool-b"}],
        "detect": {"type": "binary", "command": "fake-tool-b --version"},
    }
    ctx.registry = [fake_tool, fake_tool_b]

    with pytest.raises(ConflictError):
        install_tool("fake_tool_a", dry_run=False)


def test_install_dry_run_does_not_write(patched_env):
    from cc_manager.commands.install import install_tool
    with patch("cc_manager.commands.install.run_cmd", return_value=(0, "")):
        install_tool("rtk", dry_run=True)
    # Should NOT be in installed.json
    installed = get_installed(patched_env)
    assert "rtk" not in installed["tools"]


def test_install_logs_event(patched_env):
    from cc_manager.commands.install import install_tool
    with patch("cc_manager.commands.install.run_cmd", return_value=(0, "rtk 0.25.0")):
        install_tool("rtk", dry_run=False)
    lines = patched_env["store_path"].read_text().strip().splitlines()
    events = [json.loads(l) for l in lines]
    assert any(e["event"] == "install" and e.get("tool") == "rtk" for e in events)


def test_install_unknown_tool_raises(patched_env):
    from cc_manager.commands.install import install_tool, ToolNotFoundError
    with pytest.raises(ToolNotFoundError):
        install_tool("nonexistent_tool_xyz", dry_run=False)
