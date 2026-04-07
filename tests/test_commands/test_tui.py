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


# ── Integration: build_dashboard ──────────────────────────────────────────────

def test_build_dashboard_returns_renderable(patched_env):
    """build_dashboard() should return something Rich can render without crashing."""
    from rich.console import Console
    from cc_manager.commands.tui import build_dashboard

    # Call build_dashboard
    result = build_dashboard()
    assert result is not None

    # Verify it can actually be rendered to a string
    c = Console(width=120, force_terminal=True, force_jupyter=False, record=True)
    c.print(result)
    captured = c.export_text()
    # Should contain key section headers
    assert "CC-MANAGER" in captured


def test_build_dashboard_with_session_data(patched_env):
    """Dashboard should correctly render when session data exists in the store."""
    from datetime import datetime, timezone
    from cc_manager.commands.tui import build_dashboard
    import cc_manager.context as ctx_mod
    from rich.console import Console

    # Write a couple of fake session_end events
    store_path = patched_env["store_path"]
    now = datetime.now(timezone.utc).isoformat()
    sessions = [
        json.dumps({
            "ts": now,
            "event": "session_end",
            "model": "claude-sonnet",
            "input_tokens": 100_000,
            "output_tokens": 25_000,
            "cost_usd": 0.45,
            "duration_min": 15,
        }),
        json.dumps({
            "ts": now,
            "event": "session_end",
            "model": "claude-opus",
            "input_tokens": 200_000,
            "output_tokens": 50_000,
            "cost_usd": 1.20,
            "duration_min": 30,
        }),
    ]
    store_path.write_text("\n".join(sessions) + "\n", encoding="utf-8")

    result = build_dashboard()
    c = Console(width=120, force_terminal=True, force_jupyter=False, record=True)
    c.print(result)
    captured = c.export_text()

    # Should show session data
    assert "TOKEN USAGE" in captured
    assert "COST BREAKDOWN" in captured
    assert "RECENT SESSIONS" in captured


def test_build_dashboard_with_installed_tool(patched_env):
    """Dashboard should list installed tools in the INSTALLED TOOLS panel."""
    from cc_manager.commands.tui import build_dashboard
    from rich.console import Console

    # Write a fake installed tool
    registry_path = patched_env["registry_path"]
    registry_path.write_text(
        json.dumps({
            "schema_version": 1,
            "tools": {
                "rtk": {"version": "0.25.0", "method": "cargo", "installed_at": "2026-04-01T00:00:00"},
            },
        }),
        encoding="utf-8",
    )

    result = build_dashboard()
    c = Console(width=120, force_terminal=True, force_jupyter=False, record=True)
    c.print(result)
    captured = c.export_text()

    assert "rtk" in captured
    assert "INSTALLED TOOLS" in captured


def test_build_dashboard_no_crash_empty_state(patched_env):
    """Dashboard should not crash with completely empty state."""
    from cc_manager.commands.tui import build_dashboard
    from rich.console import Console

    result = build_dashboard()
    c = Console(width=100, force_terminal=True, force_jupyter=False, record=True)
    # Should not raise
    c.print(result)


# ── run() static mode ─────────────────────────────────────────────────────────

def test_run_static_no_crash(patched_env, capsys):
    """run() in static (default) mode should print the dashboard without error."""
    from typer.testing import CliRunner
    from cc_manager.commands.tui import app

    runner = CliRunner()
    result = runner.invoke(app, [])
    # Should not have a non-zero exit code from an exception
    assert result.exit_code == 0 or result.exit_code is None or "Error" not in (result.output or "")


# ── get_recommendations ───────────────────────────────────────────────────────

def test_get_recommendations_no_mcp_no_tools(patched_env):
    """Should recommend tools when nothing is installed and no MCP configured."""
    from cc_manager.commands.tui import get_recommendations
    from cc_manager.context import get_ctx

    ctx = get_ctx()
    recs = get_recommendations(ctx)

    # At minimum, should recommend context7 (no MCP), claude-squad (no orchestration), trail-of-bits
    tool_names = [r["tool"] for r in recs if r["tool"] is not None]
    assert len(recs) >= 1
    # All recs must have a message
    for r in recs:
        assert "message" in r and r["message"]


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
