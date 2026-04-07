"""cc-manager event store — append-only JSONL."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_ts(ts_str: str) -> datetime:
    """Parse an ISO timestamp, ensuring it is timezone-aware (UTC)."""
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _ensure_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (UTC if naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class Store:
    """Append-only JSONL event store."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def append(self, event: str, **kwargs: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **kwargs}
        with open(self.path, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def _read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return records

    def query(
        self,
        event: str | None = None,
        since: datetime | None = None,
        tool: str | None = None,
        session: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        records = self._read_all()
        if event is not None:
            records = [r for r in records if r.get("event") == event]
        if tool is not None:
            records = [r for r in records if r.get("tool") == tool]
        if session is not None:
            records = [r for r in records if r.get("session") == session]
        if since is not None:
            since_aware = _ensure_aware(since)
            records = [
                r for r in records
                if _parse_ts(r["ts"]) >= since_aware
            ]
        return records[:limit]

    def tail(self, n: int = 20) -> list[dict]:
        records = self._read_all()
        return records[-n:]

    def sessions(self, since: datetime | None = None) -> list[dict]:
        return self.query(event="session_end", since=since)

    def latest(self, event: str) -> dict | None:
        records = self.query(event=event, limit=10000)
        return records[-1] if records else None
