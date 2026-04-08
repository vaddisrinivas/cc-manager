"""Additional store tests for corrupted-line handling and edge cases."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from cc_manager.store import Store


def test_read_all_skips_corrupted_lines(tmp_path, capsys):
    store_path = tmp_path / "events.jsonl"
    store_path.write_text(
        '{"ts":"2026-01-01","event":"ok"}\n'
        'NOT JSON AT ALL\n'
        '{"ts":"2026-01-02","event":"ok2"}\n',
        encoding="utf-8",
    )
    store = Store(store_path)
    records = store._read_all()
    assert len(records) == 2
    assert records[0]["event"] == "ok"
    assert records[1]["event"] == "ok2"
    # Warning should appear on stderr
    captured = capsys.readouterr()
    assert "skipped 1 corrupted" in captured.err


def test_read_all_all_corrupted(tmp_path, capsys):
    store_path = tmp_path / "events.jsonl"
    store_path.write_text("bad\nalso bad\n", encoding="utf-8")
    store = Store(store_path)
    records = store._read_all()
    assert records == []
    captured = capsys.readouterr()
    assert "skipped 2 corrupted" in captured.err


def test_append_and_query_roundtrip(tmp_path):
    store = Store(tmp_path / "events.jsonl")
    store.append("test_event", key="value", num=42)
    records = store.query(event="test_event")
    assert len(records) == 1
    assert records[0]["key"] == "value"
    assert records[0]["num"] == 42


def test_query_by_session(tmp_path):
    store = Store(tmp_path / "events.jsonl")
    store.append("tool_use", session="abc", tool="bash")
    store.append("tool_use", session="xyz", tool="read")
    records = store.query(session="abc")
    assert len(records) == 1
    assert records[0]["tool"] == "bash"


def test_latest_returns_most_recent(tmp_path):
    store = Store(tmp_path / "events.jsonl")
    store.append("install", tool="rtk", version="1.0")
    store.append("install", tool="context7", version="2.0")
    latest = store.latest("install")
    assert latest["tool"] == "context7"


def test_sessions_filters_correctly(tmp_path):
    store = Store(tmp_path / "events.jsonl")
    store.append("session_start")
    store.append("session_end", cost_usd=0.05)
    store.append("session_end", cost_usd=0.10)
    sessions = store.sessions()
    assert len(sessions) == 2
    assert all(s["event"] == "session_end" for s in sessions)


def test_tail_with_corrupted_lines(tmp_path):
    store_path = tmp_path / "events.jsonl"
    lines = []
    for i in range(5):
        lines.append(json.dumps({"ts": f"2026-01-0{i+1}", "event": f"ev{i}"}))
    lines.insert(2, "CORRUPTED")
    store_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    store = Store(store_path)
    records = store.tail(10)
    # Should have 5 valid records, skip corrupted
    assert len(records) == 5
