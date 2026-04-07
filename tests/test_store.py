"""Tests for cc_manager.store"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cc_manager.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "events.jsonl")


def test_append_creates_file(store, tmp_path):
    store.append("install", tool="rtk", version="0.25.0")
    assert store.path.exists()


def test_append_writes_jsonl(store):
    store.append("install", tool="rtk", version="0.25.0")
    lines = store.path.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event"] == "install"
    assert record["tool"] == "rtk"
    assert record["version"] == "0.25.0"
    assert "ts" in record


def test_append_multiple(store):
    store.append("install", tool="rtk")
    store.append("install", tool="context7")
    store.append("doctor")
    lines = store.path.read_text().strip().splitlines()
    assert len(lines) == 3


def test_query_no_filter(store):
    store.append("install", tool="rtk")
    store.append("doctor")
    results = store.query()
    assert len(results) == 2


def test_query_filter_by_event(store):
    store.append("install", tool="rtk")
    store.append("install", tool="context7")
    store.append("doctor")
    results = store.query(event="install")
    assert len(results) == 2
    assert all(r["event"] == "install" for r in results)


def test_query_filter_by_tool(store):
    store.append("install", tool="rtk")
    store.append("install", tool="context7")
    results = store.query(tool="rtk")
    assert len(results) == 1
    assert results[0]["tool"] == "rtk"


def test_query_filter_by_session(store):
    store.append("session_start", session="abc123")
    store.append("session_end", session="abc123", cost_usd=0.5)
    store.append("session_start", session="xyz999")
    results = store.query(session="abc123")
    assert len(results) == 2
    assert all(r["session"] == "abc123" for r in results)


def test_query_limit(store):
    for i in range(10):
        store.append("install", tool=f"tool{i}")
    results = store.query(limit=5)
    assert len(results) == 5


def test_query_since(store):
    # Write a record with an old timestamp manually
    old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    with open(store.path, "a") as f:
        f.write(json.dumps({"ts": old_ts, "event": "old_event"}) + "\n")
    store.append("recent_event")
    since = datetime.now(timezone.utc) - timedelta(days=1)
    results = store.query(since=since)
    assert len(results) == 1
    assert results[0]["event"] == "recent_event"


def test_latest_returns_last_matching(store):
    store.append("install", tool="rtk")
    store.append("install", tool="context7")
    result = store.latest("install")
    assert result["tool"] == "context7"


def test_latest_returns_none_if_missing(store):
    store.append("doctor")
    assert store.latest("install") is None


def test_sessions_returns_session_end_events(store):
    store.append("session_start", session="a")
    store.append("session_end", session="a", cost_usd=0.5, duration_min=30)
    store.append("session_end", session="b", cost_usd=0.8, duration_min=45)
    sessions = store.sessions()
    assert len(sessions) == 2
    assert all(s["event"] == "session_end" for s in sessions)


def test_sessions_since_filter(store):
    old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    with open(store.path, "a") as f:
        f.write(json.dumps({"ts": old_ts, "event": "session_end", "session": "old"}) + "\n")
    store.append("session_end", session="new", cost_usd=0.5)
    since = datetime.now(timezone.utc) - timedelta(days=1)
    sessions = store.sessions(since=since)
    assert len(sessions) == 1
    assert sessions[0]["session"] == "new"


def test_tail_returns_last_n(store):
    for i in range(25):
        store.append("event", index=i)
    results = store.tail(n=10)
    assert len(results) == 10
    # Should be last 10
    indices = [r["index"] for r in results]
    assert indices == list(range(15, 25))


def test_tail_default_20(store):
    for i in range(30):
        store.append("event", index=i)
    results = store.tail()
    assert len(results) == 20


def test_store_handles_empty_file(store):
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text("")
    results = store.query()
    assert results == []
    assert store.latest("anything") is None
    assert store.tail() == []
