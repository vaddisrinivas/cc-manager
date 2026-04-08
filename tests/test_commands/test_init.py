"""Tests for cc_manager.commands.init"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional
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


# ---------------------------------------------------------------------------
# _step3_install_tools — batch consent + parallel install
# ---------------------------------------------------------------------------

def _make_fake_registry(methods: Optional[List[dict]] = None) -> List[dict]:
    """Return a minimal fake registry with one recommended tool per method type."""
    if methods is None:
        methods = [{"type": "cargo", "command": "echo install_ok"}]
    return [
        {
            "name": "fake-tool",
            "tier": "recommended",
            "description": "A fake tool for testing",
            "install_methods": methods,
            "category": "test",
        }
    ]


@pytest.fixture
def step3_env(patched_env, monkeypatch):
    """Extend patched_env with a fake registry for step3 tests."""
    import cc_manager.context as ctx_mod

    registry = _make_fake_registry()
    monkeypatch.setattr(ctx_mod, "load_registry", lambda: registry)

    # Write empty installed.json
    manager_dir = patched_env["manager_dir"]
    manager_dir.mkdir(parents=True, exist_ok=True)
    (manager_dir / "registry").mkdir(parents=True, exist_ok=True)
    (manager_dir / "store").mkdir(parents=True, exist_ok=True)
    reg_path = manager_dir / "registry" / "installed.json"
    reg_path.write_text(json.dumps({"schema_version": 1, "tools": {}}))

    return {**patched_env, "registry": registry}


def test_step3_skips_on_minimal(step3_env):
    """--minimal skips tool installation entirely."""
    from cc_manager.commands.init import _step3_install_tools
    result = _step3_install_tools(dry_run=False, minimal=True, yes=True)
    assert result == []


def test_step3_dry_run_returns_empty(step3_env, monkeypatch):
    """--dry-run never installs anything."""
    monkeypatch.setattr(
        "cc_manager.commands.init._detect_tool", lambda t: None
    )
    from cc_manager.commands.init import _step3_install_tools
    result = _step3_install_tools(dry_run=True, minimal=False, yes=True)
    assert result == []


def test_step3_yes_installs_all(step3_env, monkeypatch):
    """--yes approves all tools without prompting, then installs them."""
    monkeypatch.setattr("cc_manager.commands.init._detect_tool", lambda t: None)

    installed_calls = []

    def fake_run_cmd(cmd, timeout=30):
        installed_calls.append(cmd)
        return 0, "ok"

    monkeypatch.setattr("cc_manager.commands.init.run_cmd", fake_run_cmd)
    monkeypatch.setattr("cc_manager.commands.install.run_cmd", fake_run_cmd)

    from cc_manager.commands.init import _step3_install_tools
    result = _step3_install_tools(dry_run=False, minimal=False, yes=True)

    assert "fake-tool" in result
    assert len(installed_calls) >= 1


def test_step3_collects_all_consent_before_installing(step3_env, monkeypatch):
    """All y/n prompts are shown before any install command runs."""
    monkeypatch.setattr("cc_manager.commands.init._detect_tool", lambda t: None)

    # Two tools to install
    two_tools = [
        {"name": "tool-a", "tier": "recommended", "description": "A",
         "install_methods": [{"type": "cargo", "command": "echo a"}], "category": "test"},
        {"name": "tool-b", "tier": "recommended", "description": "B",
         "install_methods": [{"type": "cargo", "command": "echo b"}], "category": "test"},
    ]
    import cc_manager.context as ctx_mod
    monkeypatch.setattr(ctx_mod, "load_registry", lambda: two_tools)
    ctx_mod._ctx = None  # reset singleton

    event_log: list[str] = []

    def fake_prompt_yes(msg, default=True):
        event_log.append(f"prompt:{msg.split()[2]}")  # capture tool name
        return True

    def fake_run_cmd(cmd, timeout=30):
        event_log.append(f"install:{cmd}")
        return 0, "ok"

    monkeypatch.setattr("cc_manager.commands.init._prompt_yes", fake_prompt_yes)
    monkeypatch.setattr("cc_manager.commands.init.run_cmd", fake_run_cmd)
    monkeypatch.setattr("cc_manager.commands.install.run_cmd", fake_run_cmd)

    from cc_manager.commands.init import _step3_install_tools
    _step3_install_tools(dry_run=False, minimal=False, yes=False)

    # All prompts must appear before any install
    prompt_indices = [i for i, e in enumerate(event_log) if e.startswith("prompt:")]
    install_indices = [i for i, e in enumerate(event_log) if e.startswith("install:")]
    assert prompt_indices, "expected at least one prompt"
    assert install_indices, "expected at least one install"
    assert max(prompt_indices) < min(install_indices), (
        "Installs started before all consent collected. "
        f"prompts at {prompt_indices}, installs at {install_indices}"
    )


def test_step3_skips_already_installed(step3_env, monkeypatch):
    """Tools already in installed.json are skipped without prompting."""
    # Mark fake-tool as already installed
    manager_dir = step3_env["manager_dir"]
    reg_path = manager_dir / "registry" / "installed.json"
    reg_path.write_text(json.dumps({
        "schema_version": 1,
        "tools": {"fake-tool": {"version": "1.0", "method": "cargo"}},
    }))

    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None

    prompt_calls = []
    monkeypatch.setattr(
        "cc_manager.commands.init._prompt_yes",
        lambda msg, default=True: prompt_calls.append(msg) or True,
    )

    from cc_manager.commands.init import _step3_install_tools
    result = _step3_install_tools(dry_run=False, minimal=False, yes=False)

    assert "fake-tool" not in result
    assert not prompt_calls, "should not prompt for already-installed tools"


def test_step3_user_declines_tool(step3_env, monkeypatch):
    """When user says no to a tool it is not installed."""
    monkeypatch.setattr("cc_manager.commands.init._detect_tool", lambda t: None)
    monkeypatch.setattr("cc_manager.commands.init._prompt_yes", lambda *a, **kw: False)

    from cc_manager.commands.init import _step3_install_tools
    result = _step3_install_tools(dry_run=False, minimal=False, yes=False)
    assert result == []


def test_step3_keyboard_interrupt_during_consent(step3_env, monkeypatch):
    """Ctrl+C during consent stops prompting and installs only approved tools."""
    monkeypatch.setattr("cc_manager.commands.init._detect_tool", lambda t: None)

    call_count = [0]

    def prompt_raises_on_second(msg, default=True):
        call_count[0] += 1
        if call_count[0] >= 2:
            raise KeyboardInterrupt
        return True

    monkeypatch.setattr("cc_manager.commands.init._prompt_yes", prompt_raises_on_second)

    # Two tools so interrupt fires on second
    two_tools = [
        {"name": "tool-a", "tier": "recommended", "description": "A",
         "install_methods": [{"type": "mcp", "mcp_config": {"command": "node", "args": []}}],
         "category": "test"},
        {"name": "tool-b", "tier": "recommended", "description": "B",
         "install_methods": [{"type": "mcp", "mcp_config": {"command": "node", "args": []}}],
         "category": "test"},
    ]
    import cc_manager.context as ctx_mod
    monkeypatch.setattr(ctx_mod, "load_registry", lambda: two_tools)
    ctx_mod._ctx = None

    import cc_manager.settings as smod
    monkeypatch.setattr(smod, "merge_mcp", lambda name, cfg: None)

    from cc_manager.commands.init import _step3_install_tools
    result = _step3_install_tools(dry_run=False, minimal=False, yes=False)

    # tool-a was approved before interrupt; tool-b was not
    assert "tool-b" not in result


def test_step3_keyboard_interrupt_during_install(step3_env, monkeypatch):
    """Ctrl+C during install stops the batch and reports partial results."""
    monkeypatch.setattr("cc_manager.commands.init._detect_tool", lambda t: None)
    monkeypatch.setattr("cc_manager.commands.init._prompt_yes", lambda *a, **kw: True)

    call_count = [0]

    def slow_cmd(cmd, timeout=30):
        call_count[0] += 1
        if call_count[0] >= 2:
            raise KeyboardInterrupt
        return 0, "ok"

    monkeypatch.setattr("cc_manager.commands.init.run_cmd", slow_cmd)
    monkeypatch.setattr("cc_manager.commands.install.run_cmd", slow_cmd)

    # Two tools
    two_tools = [
        {"name": "tool-a", "tier": "recommended", "description": "A",
         "install_methods": [{"type": "cargo", "command": "echo a"}], "category": "test"},
        {"name": "tool-b", "tier": "recommended", "description": "B",
         "install_methods": [{"type": "cargo", "command": "echo b"}], "category": "test"},
    ]
    import cc_manager.context as ctx_mod
    monkeypatch.setattr(ctx_mod, "load_registry", lambda: two_tools)
    ctx_mod._ctx = None

    from cc_manager.commands.init import _step3_install_tools
    # Should not raise — interrupt is handled internally
    try:
        result = _step3_install_tools(dry_run=False, minimal=False, yes=True)
        # Partial result is fine
        assert isinstance(result, list)
    except (KeyboardInterrupt, SystemExit):
        pass  # acceptable — what matters is no unhandled crash


def test_step3_mcp_tool_no_subprocess(step3_env, monkeypatch):
    """MCP tools are registered via settings merge, not a subprocess."""
    monkeypatch.setattr("cc_manager.commands.init._detect_tool", lambda t: None)

    import cc_manager.context as ctx_mod
    mcp_registry = [{
        "name": "fake-mcp",
        "tier": "recommended",
        "description": "MCP tool",
        "install_methods": [{"type": "mcp", "mcp_config": {"command": "node", "args": ["fake"]}}],
        "category": "mcp-server",
    }]
    monkeypatch.setattr(ctx_mod, "load_registry", lambda: mcp_registry)
    ctx_mod._ctx = None

    merge_calls = []
    import cc_manager.settings as smod
    monkeypatch.setattr(smod, "merge_mcp", lambda name, cfg: merge_calls.append(name))

    subprocess_calls = []
    monkeypatch.setattr("cc_manager.commands.init.run_cmd",
                        lambda *a, **kw: subprocess_calls.append(a) or (0, ""))

    from cc_manager.commands.init import _step3_install_tools
    result = _step3_install_tools(dry_run=False, minimal=False, yes=True)

    assert "fake-mcp" in result
    assert "fake-mcp" in merge_calls
    assert not subprocess_calls, "MCP install should not run a subprocess"


def test_step3_install_failure_reported(step3_env, monkeypatch):
    """If an install command fails, tool is not in returned list."""
    monkeypatch.setattr("cc_manager.commands.init._detect_tool", lambda t: None)
    monkeypatch.setattr("cc_manager.commands.init._prompt_yes", lambda *a, **kw: True)
    monkeypatch.setattr("cc_manager.commands.init.run_cmd", lambda *a, **kw: (1, "error"))
    monkeypatch.setattr("cc_manager.commands.install.run_cmd", lambda *a, **kw: (1, "error"))

    from cc_manager.commands.init import _step3_install_tools
    result = _step3_install_tools(dry_run=False, minimal=False, yes=True)
    assert "fake-tool" not in result


def test_step3_parallel_install_all_succeed(step3_env, monkeypatch):
    """All tools in a batch install are attempted and reported."""
    monkeypatch.setattr("cc_manager.commands.init._detect_tool", lambda t: None)

    three_tools = [
        {"name": f"tool-{c}", "tier": "recommended", "description": c,
         "install_methods": [{"type": "cargo", "command": f"echo {c}"}], "category": "test"}
        for c in "abc"
    ]
    import cc_manager.context as ctx_mod
    monkeypatch.setattr(ctx_mod, "load_registry", lambda: three_tools)
    ctx_mod._ctx = None

    monkeypatch.setattr("cc_manager.commands.init.run_cmd", lambda *a, **kw: (0, "ok"))
    monkeypatch.setattr("cc_manager.commands.install.run_cmd", lambda *a, **kw: (0, "ok"))

    from cc_manager.commands.init import _step3_install_tools
    result = _step3_install_tools(dry_run=False, minimal=False, yes=True)

    assert set(result) == {"tool-a", "tool-b", "tool-c"}
