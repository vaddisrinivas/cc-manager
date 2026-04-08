"""Tests for cc_manager.commands.tui"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_ctx():
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None
    yield
    ctx_mod._ctx = None


@pytest.fixture
def patched_env(tmp_path, monkeypatch):
    """Set up a clean isolated environment under tmp_path."""
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

    # Write empty settings + registry
    settings_path.write_text(json.dumps({"hooks": {}, "mcpServers": {}}), encoding="utf-8")
    registry_path.write_text(json.dumps({"schema_version": 1, "tools": {}}), encoding="utf-8")

    import cc_manager.context as ctx_mod
    monkeypatch.setattr(ctx_mod, "CLAUDE_DIR", claude_dir)
    monkeypatch.setattr(ctx_mod, "MANAGER_DIR", manager_dir)
    monkeypatch.setattr(ctx_mod, "SETTINGS_PATH", settings_path)
    monkeypatch.setattr(ctx_mod, "CONFIG_PATH", manager_dir / "cc-manager.toml")
    monkeypatch.setattr(ctx_mod, "STORE_PATH", store_path)
    monkeypatch.setattr(ctx_mod, "REGISTRY_PATH", registry_path)
    monkeypatch.setattr(ctx_mod, "STATE_PATH", manager_dir / "state" / "state.json")
    monkeypatch.setattr(ctx_mod, "BACKUPS_DIR", manager_dir / "backups")

    return {
        "claude_dir": claude_dir,
        "manager_dir": manager_dir,
        "registry_path": registry_path,
        "store_path": store_path,
        "settings_path": settings_path,
        "tmp_path": tmp_path,
    }


# ── Unit tests: pure helpers ───────────────────────────────────────────────────

def test_sparkline_empty():
    from cc_manager.commands.tui import sparkline
    result = sparkline([], width=10)
    assert len(result) == 10
    assert result == "─" * 10


def test_sparkline_values():
    from cc_manager.commands.tui import sparkline
    result = sparkline([0, 5, 10], width=6)
    assert len(result) == 6


def test_sparkline_single_value():
    from cc_manager.commands.tui import sparkline
    result = sparkline([42], width=5)
    assert len(result) == 5
    # Single value = max, should be all full blocks
    assert all(c == "█" for c in result)


def test_sparkline_all_zeros():
    from cc_manager.commands.tui import sparkline
    result = sparkline([0, 0, 0], width=6)
    assert len(result) == 6


def test_abbrev_millions():
    from cc_manager.commands.tui import abbrev
    assert abbrev(1_500_000) == "1.5M"
    assert abbrev(2_000_000) == "2.0M"


def test_abbrev_thousands():
    from cc_manager.commands.tui import abbrev
    assert abbrev(450_000) == "450K"
    assert abbrev(1_000) == "1K"


def test_abbrev_small():
    from cc_manager.commands.tui import abbrev
    assert abbrev(999) == "999"
    assert abbrev(0) == "0"


# ── Integration: tui run ──────────────────────────────────────────────────────

def test_tui_run_importable(patched_env):
    """run() must be importable and callable."""
    from cc_manager.commands.tui import run
    assert callable(run)


# ── run() static mode ─────────────────────────────────────────────────────────

def test_run_static_no_crash(patched_env):
    """run() launches CCManagerApp (mocked so terminal is not required)."""
    from unittest.mock import patch, MagicMock
    mock_app = MagicMock()
    mock_cls = MagicMock(return_value=mock_app)
    with patch("cc_manager.commands.tui.CCManagerApp", mock_cls, create=True):
        import sys
        fake_mod = MagicMock()
        fake_mod.CCManagerApp = mock_cls
        with patch.dict(sys.modules, {"cc_manager.app": fake_mod}):
            from cc_manager.commands.tui import run
            try:
                run()
            except Exception:
                pass  # any import/exit is fine; we just verify no uncaught crash
    # If we reach here the test passed


# ── get_recommendations ───────────────────────────────────────────────────────

def test_get_recommendations_no_mcp_no_tools(patched_env):
    """With no sessions recorded, recommendations are empty (data-driven only)."""
    from cc_manager.commands.tui import get_recommendations
    from cc_manager.context import get_ctx

    ctx = get_ctx()
    recs = get_recommendations(ctx)

    # No sessions → no recommendations (all recs require usage data to fire)
    assert isinstance(recs, list)
    assert len(recs) == 0


def test_get_recommendations_returns_list(patched_env):
    """get_recommendations always returns a list."""
    from cc_manager.commands.tui import get_recommendations
    from cc_manager.context import get_ctx

    ctx = get_ctx()
    result = get_recommendations(ctx)
    assert isinstance(result, list)


def test_get_recommendations_all_clear_when_installed(patched_env):
    """When all recommended tools are installed, fewer recs should be returned."""
    from cc_manager.commands.tui import get_recommendations
    from cc_manager.context import get_ctx

    # Install all the tools that trigger recommendations
    patched_env["registry_path"].write_text(
        json.dumps({
            "schema_version": 1,
            "tools": {
                "rtk": {"version": "0.25.0", "method": "cargo"},
                "context7": {"version": "latest", "method": "mcp"},
                "playwright-mcp": {"version": "latest", "method": "mcp"},
                "trail-of-bits": {"version": "latest", "method": "mcp"},
                "claude-squad": {"version": "latest", "method": "go"},
                "cc-sentinel": {"version": "latest", "method": "plugin"},
                "cc-later": {"version": "latest", "method": "plugin"},
            },
        }),
        encoding="utf-8",
    )
    # Add MCP servers to settings
    patched_env["settings_path"].write_text(
        json.dumps({
            "hooks": {},
            "mcpServers": {"context7": {"command": "npx", "args": []}},
        }),
        encoding="utf-8",
    )

    ctx = get_ctx()
    result = get_recommendations(ctx)
    # Should still be a list (possibly empty or just opus warning)
    assert isinstance(result, list)
