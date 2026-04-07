"""Tests for cc_manager.commands.init"""
import json
from pathlib import Path
from unittest.mock import patch

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

    import cc_manager.context as ctx_mod
    import cc_manager.settings as smod
    monkeypatch.setattr(ctx_mod, "CLAUDE_DIR", claude_dir)
    monkeypatch.setattr(ctx_mod, "MANAGER_DIR", manager_dir)
    monkeypatch.setattr(ctx_mod, "SETTINGS_PATH", claude_dir / "settings.json")
    monkeypatch.setattr(ctx_mod, "CONFIG_PATH", manager_dir / "cc-manager.toml")
    monkeypatch.setattr(ctx_mod, "STORE_PATH", manager_dir / "store" / "events.jsonl")
    monkeypatch.setattr(ctx_mod, "REGISTRY_PATH", manager_dir / "registry" / "installed.json")
    monkeypatch.setattr(ctx_mod, "STATE_PATH", manager_dir / "state" / "state.json")
    monkeypatch.setattr(ctx_mod, "BACKUPS_DIR", manager_dir / "backups")
    monkeypatch.setattr(smod, "SETTINGS_PATH", claude_dir / "settings.json")
    monkeypatch.setattr(smod, "LOCK_PATH", manager_dir / ".settings.lock")
    monkeypatch.setattr(smod, "BACKUPS_DIR", manager_dir / "backups")

    return {"claude_dir": claude_dir, "manager_dir": manager_dir}


def test_init_creates_directory_structure(patched_env):
    from cc_manager.commands.init import run_init
    run_init(dry_run=False, minimal=True, yes=True)
    manager_dir = patched_env["manager_dir"]
    assert (manager_dir / "store").exists()
    assert (manager_dir / "backups").exists()
    assert (manager_dir / "registry").exists()
    assert (manager_dir / "state").exists()


def test_init_writes_config(patched_env):
    from cc_manager.commands.init import run_init
    run_init(dry_run=False, minimal=True, yes=True)
    config_path = patched_env["manager_dir"] / "cc-manager.toml"
    assert config_path.exists()
    content = config_path.read_text()
    assert "schema_version" in content


def test_init_registers_hooks(patched_env):
    from cc_manager.commands.init import run_init
    import cc_manager.settings as smod
    run_init(dry_run=False, minimal=True, yes=True)
    settings = smod.read()
    assert "hooks" in settings
    hooks = settings["hooks"]
    # Should have at least Stop and SessionStart
    hook_events = set(hooks.keys())
    assert len(hook_events) >= 2


def test_init_dry_run_does_not_create_dirs(patched_env):
    from cc_manager.commands.init import run_init
    run_init(dry_run=True, minimal=True, yes=True)
    manager_dir = patched_env["manager_dir"]
    # In dry_run mode, directories should NOT be created
    assert not manager_dir.exists()


def test_init_backs_up_existing_settings(patched_env):
    # Create existing settings
    settings_path = patched_env["claude_dir"] / "settings.json"
    settings_path.write_text(json.dumps({"existing": True}))
    from cc_manager.commands.init import run_init
    run_init(dry_run=False, minimal=True, yes=True)
    # A backup should exist
    import cc_manager.settings as smod
    backups = smod.backup_list()
    assert len(backups) >= 1


def test_init_minimal_no_tools(patched_env):
    from cc_manager.commands.init import run_init
    with patch("cc_manager.commands.install.run_cmd", return_value=(0, "")):
        run_init(dry_run=False, minimal=True, yes=True)
    registry_path = patched_env["manager_dir"] / "registry" / "installed.json"
    if registry_path.exists():
        data = json.loads(registry_path.read_text())
        # With minimal=True, no tools should be installed
        assert len(data.get("tools", {})) == 0


def test_init_installs_hook_py(patched_env):
    from cc_manager.commands.init import run_init
    run_init(dry_run=False, minimal=True, yes=True)
    hook_py = patched_env["manager_dir"] / "hook.py"
    assert hook_py.exists()


def test_init_logs_event(patched_env):
    from cc_manager.commands.init import run_init
    run_init(dry_run=False, minimal=True, yes=True)
    store_path = patched_env["manager_dir"] / "store" / "events.jsonl"
    assert store_path.exists()
    lines = store_path.read_text().strip().splitlines()
    events = [json.loads(l) for l in lines if l]
    assert any(e["event"] == "init" for e in events)


def test_init_idempotent(patched_env):
    """Running init twice should not fail."""
    from cc_manager.commands.init import run_init
    run_init(dry_run=False, minimal=True, yes=True)
    run_init(dry_run=False, minimal=True, yes=True)
    manager_dir = patched_env["manager_dir"]
    assert (manager_dir / "store").exists()
