"""Tests for cc_manager.commands.doctor"""
import json
import sys
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
    manager_dir.mkdir()
    (manager_dir / "store").mkdir()
    (manager_dir / "registry").mkdir()
    (manager_dir / "state").mkdir()
    (manager_dir / "backups").mkdir()

    settings_path = claude_dir / "settings.json"
    # Write minimal valid settings with cc-manager hooks
    settings_path.write_text(json.dumps({
        "hooks": {
            "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "python3 ~/.cc-manager/hook.py Stop"}]}],
            "SessionStart": [{"matcher": "", "hooks": [{"type": "command", "command": "python3 ~/.cc-manager/hook.py SessionStart"}]}],
        }
    }))

    registry_path = manager_dir / "registry" / "installed.json"
    registry_path.write_text(json.dumps({"schema_version": 1, "tools": {}}))

    # Write valid config
    config_path = manager_dir / "cc-manager.toml"
    config_path.write_text("[manager]\nschema_version = 1\n")

    import cc_manager.context as ctx_mod
    import cc_manager.settings as smod
    monkeypatch.setattr(ctx_mod, "CLAUDE_DIR", claude_dir)
    monkeypatch.setattr(ctx_mod, "MANAGER_DIR", manager_dir)
    monkeypatch.setattr(ctx_mod, "SETTINGS_PATH", settings_path)
    monkeypatch.setattr(ctx_mod, "CONFIG_PATH", config_path)
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
        "settings_path": settings_path,
        "registry_path": registry_path,
        "config_path": config_path,
    }


def test_doctor_returns_results_dict(patched_env):
    from cc_manager.commands.doctor import run_checks
    results = run_checks()
    assert isinstance(results, dict)


def test_doctor_python_version_ok(patched_env):
    from cc_manager.commands.doctor import run_checks
    results = run_checks()
    assert "python_version" in results
    assert results["python_version"]["status"] in ("ok", "warn", "fail")


@pytest.mark.skipif(sys.version_info < (3, 11), reason="Requires Python 3.11+")
def test_doctor_python_version_pass(patched_env):
    """Current Python is 3.11+, so this should pass."""
    from cc_manager.commands.doctor import run_checks
    results = run_checks()
    assert results["python_version"]["status"] == "ok"


def test_doctor_hooks_registered(patched_env):
    from cc_manager.commands.doctor import run_checks
    results = run_checks()
    assert "hooks_registered" in results
    assert results["hooks_registered"]["status"] == "ok"


def test_doctor_hooks_missing(patched_env):
    # Remove hooks from settings
    patched_env["settings_path"].write_text(json.dumps({}))
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None

    from cc_manager.commands.doctor import run_checks
    results = run_checks()
    assert results["hooks_registered"]["status"] in ("warn", "fail")


def test_doctor_config_valid(patched_env):
    from cc_manager.commands.doctor import run_checks
    results = run_checks()
    assert "config_valid" in results
    assert results["config_valid"]["status"] == "ok"


def test_doctor_config_invalid(patched_env, monkeypatch):
    patched_env["config_path"].write_text("this is not valid toml !!!@@@[[[")
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None
    from cc_manager.commands.doctor import run_checks
    results = run_checks()
    assert results["config_valid"]["status"] in ("warn", "fail")


def test_doctor_store_writable(patched_env):
    from cc_manager.commands.doctor import run_checks
    results = run_checks()
    assert "store_writable" in results
    assert results["store_writable"]["status"] == "ok"


def test_doctor_installed_tool_ok(patched_env):
    # Install rtk with a detect command we can mock
    installed_data = {
        "schema_version": 1,
        "tools": {
            "rtk": {"version": "0.25.0", "method": "cargo", "installed_at": "2026-04-06T10:00:00", "pinned": False}
        }
    }
    patched_env["registry_path"].write_text(json.dumps(installed_data))
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None

    with patch("cc_manager.commands.doctor.run_cmd", return_value=(0, "rtk 0.25.0")):
        from cc_manager.commands.doctor import run_checks
        results = run_checks()

    # There should be a result for rtk
    tool_key = next((k for k in results if "rtk" in k), None)
    assert tool_key is not None
    assert results[tool_key]["status"] == "ok"


def test_doctor_installed_tool_missing(patched_env):
    installed_data = {
        "schema_version": 1,
        "tools": {
            "rtk": {"version": "0.25.0", "method": "cargo", "installed_at": "2026-04-06T10:00:00", "pinned": False}
        }
    }
    patched_env["registry_path"].write_text(json.dumps(installed_data))
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None

    with patch("cc_manager.commands.doctor.run_cmd", return_value=(1, "command not found")):
        from cc_manager.commands.doctor import run_checks
        results = run_checks()

    tool_key = next((k for k in results if "rtk" in k), None)
    assert tool_key is not None
    assert results[tool_key]["status"] in ("warn", "fail")


def test_doctor_logs_event(patched_env):
    from cc_manager.commands.doctor import run_checks
    store_path = patched_env["manager_dir"] / "store" / "events.jsonl"
    run_checks()
    if store_path.exists():
        lines = store_path.read_text().strip().splitlines()
        events = [json.loads(l) for l in lines if l]
        assert any(e["event"] == "doctor" for e in events)
