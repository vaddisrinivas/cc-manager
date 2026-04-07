"""Tests for cc_manager.commands.analyze"""
import json
from datetime import datetime, timedelta, timezone
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
    store_path = manager_dir / "store" / "events.jsonl"

    import cc_manager.context as ctx_mod
    import cc_manager.settings as smod
    monkeypatch.setattr(ctx_mod, "CLAUDE_DIR", claude_dir)
    monkeypatch.setattr(ctx_mod, "MANAGER_DIR", manager_dir)
    monkeypatch.setattr(ctx_mod, "SETTINGS_PATH", settings_path)
    monkeypatch.setattr(ctx_mod, "CONFIG_PATH", manager_dir / "cc-manager.toml")
    monkeypatch.setattr(ctx_mod, "STORE_PATH", store_path)
    monkeypatch.setattr(ctx_mod, "REGISTRY_PATH", manager_dir / "registry" / "installed.json")
    monkeypatch.setattr(ctx_mod, "STATE_PATH", manager_dir / "state" / "state.json")
    monkeypatch.setattr(ctx_mod, "BACKUPS_DIR", manager_dir / "backups")
    monkeypatch.setattr(smod, "SETTINGS_PATH", settings_path)
    monkeypatch.setattr(smod, "LOCK_PATH", manager_dir / ".settings.lock")
    monkeypatch.setattr(smod, "BACKUPS_DIR", manager_dir / "backups")

    return {
        "claude_dir": claude_dir,
        "manager_dir": manager_dir,
        "store_path": store_path,
    }


def write_events(store_path, events):
    store_path.parent.mkdir(parents=True, exist_ok=True)
    with open(store_path, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


def make_session_end(session_id, days_ago=1, input_tokens=100000, output_tokens=20000, cache_read=50000, duration_min=30, model="sonnet"):
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {
        "ts": ts,
        "event": "session_end",
        "session": session_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read": cache_read,
        "duration_min": duration_min,
        "model": model,
        "cost_usd": 0.5,
    }


def test_analyze_empty_store(patched_env):
    from cc_manager.commands.analyze import compute_stats
    stats = compute_stats(period_days=7)
    assert stats["sessions"] == 0
    assert stats["total_input_tokens"] == 0
    assert stats["total_output_tokens"] == 0


def test_analyze_session_count(patched_env):
    events = [
        make_session_end("s1", days_ago=1),
        make_session_end("s2", days_ago=2),
        make_session_end("s3", days_ago=3),
    ]
    write_events(patched_env["store_path"], events)
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None

    from cc_manager.commands.analyze import compute_stats
    stats = compute_stats(period_days=7)
    assert stats["sessions"] == 3


def test_analyze_token_totals(patched_env):
    events = [
        make_session_end("s1", input_tokens=100000, output_tokens=20000, cache_read=50000),
        make_session_end("s2", input_tokens=200000, output_tokens=40000, cache_read=80000),
    ]
    write_events(patched_env["store_path"], events)
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None

    from cc_manager.commands.analyze import compute_stats
    stats = compute_stats(period_days=7)
    assert stats["total_input_tokens"] == 300000
    assert stats["total_output_tokens"] == 60000
    assert stats["total_cache_read"] == 130000


def test_analyze_period_filter(patched_env):
    events = [
        make_session_end("s1", days_ago=1),
        make_session_end("s2", days_ago=5),
        make_session_end("s3", days_ago=10),  # outside 7d window
    ]
    write_events(patched_env["store_path"], events)
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None

    from cc_manager.commands.analyze import compute_stats
    stats = compute_stats(period_days=7)
    assert stats["sessions"] == 2


def test_analyze_avg_duration(patched_env):
    events = [
        make_session_end("s1", duration_min=30),
        make_session_end("s2", duration_min=60),
    ]
    write_events(patched_env["store_path"], events)
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None

    from cc_manager.commands.analyze import compute_stats
    stats = compute_stats(period_days=7)
    assert stats["avg_duration_min"] == 45.0


def test_analyze_model_breakdown(patched_env):
    events = [
        make_session_end("s1", model="sonnet"),
        make_session_end("s2", model="sonnet"),
        make_session_end("s3", model="opus"),
    ]
    write_events(patched_env["store_path"], events)
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None

    from cc_manager.commands.analyze import compute_stats
    stats = compute_stats(period_days=7)
    assert "model_breakdown" in stats
    assert stats["model_breakdown"]["sonnet"] == 2
    assert stats["model_breakdown"]["opus"] == 1


def test_analyze_compact_frequency(patched_env):
    now = datetime.now(timezone.utc)
    events = [
        {"ts": (now - timedelta(days=1)).isoformat(), "event": "session_end", "session": "s1", "input_tokens": 100000, "output_tokens": 10000, "cache_read": 0, "duration_min": 30, "model": "sonnet"},
        {"ts": (now - timedelta(days=1, hours=1)).isoformat(), "event": "compact", "session": "s1", "trigger": "auto"},
        {"ts": (now - timedelta(days=1, hours=2)).isoformat(), "event": "compact", "session": "s1", "trigger": "auto"},
    ]
    write_events(patched_env["store_path"], events)
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None

    from cc_manager.commands.analyze import compute_stats
    stats = compute_stats(period_days=7)
    assert "compaction_count" in stats
    assert stats["compaction_count"] >= 2


def test_analyze_30d_period(patched_env):
    events = [
        make_session_end("s1", days_ago=1),
        make_session_end("s2", days_ago=20),
        make_session_end("s3", days_ago=35),  # outside 30d window
    ]
    write_events(patched_env["store_path"], events)
    import cc_manager.context as ctx_mod
    ctx_mod._ctx = None

    from cc_manager.commands.analyze import compute_stats
    stats = compute_stats(period_days=30)
    assert stats["sessions"] == 2
