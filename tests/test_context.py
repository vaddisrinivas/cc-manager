"""Tests for cc_manager.context"""
import json
from datetime import timedelta
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def reset_ctx():
    """Reset the global singleton between tests."""
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None
    yield
    ctx_mod._ctx = None


@pytest.fixture
def patched_dirs(tmp_path, monkeypatch):
    claude_dir = tmp_path / ".claude"
    manager_dir = tmp_path / ".cc-manager"
    claude_dir.mkdir()
    manager_dir.mkdir()
    (manager_dir / "store").mkdir()
    (manager_dir / "registry").mkdir()
    (manager_dir / "state").mkdir()
    (manager_dir / "backups").mkdir()

    import cc_manager.context as ctx_mod
    monkeypatch.setattr(ctx_mod, "CLAUDE_DIR", claude_dir)
    monkeypatch.setattr(ctx_mod, "MANAGER_DIR", manager_dir)
    monkeypatch.setattr(ctx_mod, "SETTINGS_PATH", claude_dir / "settings.json")
    monkeypatch.setattr(ctx_mod, "CONFIG_PATH", manager_dir / "cc-manager.toml")
    monkeypatch.setattr(ctx_mod, "STORE_PATH", manager_dir / "store" / "events.jsonl")
    monkeypatch.setattr(ctx_mod, "REGISTRY_PATH", manager_dir / "registry" / "installed.json")
    monkeypatch.setattr(ctx_mod, "STATE_PATH", manager_dir / "state" / "state.json")
    monkeypatch.setattr(ctx_mod, "BACKUPS_DIR", manager_dir / "backups")

    import cc_manager.settings as smod
    monkeypatch.setattr(smod, "SETTINGS_PATH", claude_dir / "settings.json")
    monkeypatch.setattr(smod, "LOCK_PATH", manager_dir / ".settings.lock")
    monkeypatch.setattr(smod, "BACKUPS_DIR", manager_dir / "backups")

    return {"claude_dir": claude_dir, "manager_dir": manager_dir}


def test_get_ctx_returns_context(patched_dirs):
    import cc_manager.context as ctx_mod
    ctx = ctx_mod.get_ctx()
    assert ctx is not None


def test_get_ctx_singleton(patched_dirs):
    import cc_manager.context as ctx_mod
    ctx1 = ctx_mod.get_ctx()
    ctx2 = ctx_mod.get_ctx()
    assert ctx1 is ctx2


def test_ctx_settings_empty_when_missing(patched_dirs):
    import cc_manager.context as ctx_mod
    ctx = ctx_mod.get_ctx()
    assert ctx.settings == {}


def test_ctx_settings_loaded_when_present(patched_dirs):
    settings_path = patched_dirs["claude_dir"] / "settings.json"
    settings_path.write_text(json.dumps({"mcpServers": {"x": {}}}))
    import cc_manager.context as ctx_mod
    ctx = ctx_mod.get_ctx()
    assert "mcpServers" in ctx.settings


def test_ctx_installed_default(patched_dirs):
    import cc_manager.context as ctx_mod
    ctx = ctx_mod.get_ctx()
    assert ctx.installed == {"schema_version": 1, "tools": {}}


def test_ctx_installed_loaded(patched_dirs):
    registry_path = patched_dirs["manager_dir"] / "registry" / "installed.json"
    data = {"schema_version": 1, "tools": {"rtk": {"version": "0.25.0"}}}
    registry_path.write_text(json.dumps(data))
    import cc_manager.context as ctx_mod
    ctx = ctx_mod.get_ctx()
    assert "rtk" in ctx.installed["tools"]


def test_ctx_registry_is_list(patched_dirs):
    import cc_manager.context as ctx_mod
    ctx = ctx_mod.get_ctx()
    assert isinstance(ctx.registry, list)
    assert len(ctx.registry) > 0


def test_ctx_store_is_store_instance(patched_dirs):
    import cc_manager.context as ctx_mod
    from cc_manager.store import Store
    ctx = ctx_mod.get_ctx()
    assert isinstance(ctx.store, Store)


def test_load_registry_returns_list(patched_dirs):
    import cc_manager.context as ctx_mod
    registry = ctx_mod.load_registry()
    assert isinstance(registry, list)
    assert len(registry) > 0
    # Each entry should have name and description
    for tool in registry:
        assert "name" in tool
        assert "description" in tool


def test_load_registry_has_rtk(patched_dirs):
    import cc_manager.context as ctx_mod
    registry = ctx_mod.load_registry()
    names = [t["name"] for t in registry]
    assert "rtk" in names


def test_parse_duration_days(patched_dirs):
    import cc_manager.context as ctx_mod
    td = ctx_mod.parse_duration("7d")
    assert td == timedelta(days=7)


def test_parse_duration_hours(patched_dirs):
    import cc_manager.context as ctx_mod
    td = ctx_mod.parse_duration("24h")
    assert td == timedelta(hours=24)


def test_parse_duration_30d(patched_dirs):
    import cc_manager.context as ctx_mod
    td = ctx_mod.parse_duration("30d")
    assert td == timedelta(days=30)


def test_parse_duration_1h(patched_dirs):
    import cc_manager.context as ctx_mod
    td = ctx_mod.parse_duration("1h")
    assert td == timedelta(hours=1)


def test_parse_duration_invalid(patched_dirs):
    import cc_manager.context as ctx_mod
    with pytest.raises(ValueError):
        ctx_mod.parse_duration("badformat")
