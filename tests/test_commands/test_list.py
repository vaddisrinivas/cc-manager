"""Tests for cc_manager.commands.list_cmd"""
import json
from pathlib import Path

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

    import cc_manager.context as ctx_mod
    import cc_manager.settings as smod
    monkeypatch.setattr(ctx_mod, "CLAUDE_DIR", claude_dir)
    monkeypatch.setattr(ctx_mod, "MANAGER_DIR", manager_dir)
    monkeypatch.setattr(ctx_mod, "SETTINGS_PATH", settings_path)
    monkeypatch.setattr(ctx_mod, "CONFIG_PATH", manager_dir / "cc-manager.toml")
    monkeypatch.setattr(ctx_mod, "STORE_PATH", manager_dir / "store" / "events.jsonl")
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
    }


def test_list_all_returns_tools(patched_env):
    from cc_manager.commands.list_cmd import get_tools_list
    tools = get_tools_list()
    assert isinstance(tools, list)
    assert len(tools) > 0


def test_list_all_has_required_fields(patched_env):
    from cc_manager.commands.list_cmd import get_tools_list
    tools = get_tools_list()
    for tool in tools:
        assert "name" in tool
        assert "description" in tool


def test_list_installed_filter(patched_env):
    # Install rtk
    installed_data = {
        "schema_version": 1,
        "tools": {
            "rtk": {"version": "0.25.0", "method": "cargo", "installed_at": "2026-04-06T10:00:00", "pinned": False}
        }
    }
    patched_env["registry_path"].write_text(json.dumps(installed_data))
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None

    from cc_manager.commands.list_cmd import get_tools_list
    tools = get_tools_list(installed_only=True)
    assert len(tools) >= 1
    names = [t["name"] for t in tools]
    assert "rtk" in names


def test_list_installed_only_returns_installed(patched_env):
    installed_data = {
        "schema_version": 1,
        "tools": {
            "rtk": {"version": "0.25.0", "method": "cargo", "installed_at": "2026-04-06T10:00:00", "pinned": False}
        }
    }
    patched_env["registry_path"].write_text(json.dumps(installed_data))
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None

    from cc_manager.commands.list_cmd import get_tools_list
    tools = get_tools_list(installed_only=True)
    # All returned tools should be installed
    for tool in tools:
        assert tool.get("installed") is True


def test_list_available_only(patched_env):
    installed_data = {
        "schema_version": 1,
        "tools": {
            "rtk": {"version": "0.25.0", "method": "cargo", "installed_at": "2026-04-06T10:00:00", "pinned": False}
        }
    }
    patched_env["registry_path"].write_text(json.dumps(installed_data))
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None

    from cc_manager.commands.list_cmd import get_tools_list
    tools = get_tools_list(available_only=True)
    names = [t["name"] for t in tools]
    assert "rtk" not in names


def test_list_category_filter(patched_env):
    from cc_manager.commands.list_cmd import get_tools_list
    import cc_manager.context as ctx_mod
    ctx = ctx_mod.get_ctx()
    categories = {t.get("category") for t in ctx.registry if t.get("category")}
    if not categories:
        pytest.skip("No categories in registry")
    cat = next(iter(categories))
    tools = get_tools_list(category=cat)
    for tool in tools:
        assert tool.get("category") == cat


def test_list_tier_filter(patched_env):
    from cc_manager.commands.list_cmd import get_tools_list
    tools = get_tools_list(tier="recommended")
    for tool in tools:
        assert tool.get("tier") == "recommended"


def test_list_empty_installed(patched_env):
    from cc_manager.commands.list_cmd import get_tools_list
    tools = get_tools_list(installed_only=True)
    assert tools == []
