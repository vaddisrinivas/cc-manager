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
        """Return last n records efficiently without parsing the whole file."""
        if not self.path.exists():
            return []
        try:
            with open(self.path, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                if size == 0:
                    return []
                # Read enough bytes from the end to cover n lines (~512 bytes each)
                chunk = min(size, max(n * 512, 8192))
                f.seek(-chunk, 2)
                raw = f.read()
            lines = raw.decode("utf-8", errors="replace").splitlines()
            # First line may be partial if we didn't read from the start
            if chunk < size:
                lines = lines[1:]
        except Exception:
            lines = self.path.read_text(encoding="utf-8").splitlines()

        records: list[dict] = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
            if len(records) >= n:
                break
        return list(reversed(records))

    def sessions(self, since: datetime | None = None) -> list[dict]:
        return self.query(event="session_end", since=since)

    def latest(self, event: str) -> dict | None:
        """Return the most recent record for the given event type.

        Scans from the end of the file so it is fast even on large stores.
        """
        if not self.path.exists():
            return None
        try:
            with open(self.path, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                if size == 0:
                    return None
                chunk = min(size, 65536)  # scan at most 64 KB from the end
                f.seek(-chunk, 2)
                raw = f.read()
            lines = raw.decode("utf-8", errors="replace").splitlines()
            if chunk < size:
                lines = lines[1:]  # first line may be partial
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if record.get("event") == event:
                        return record
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass
        # Fallback: full scan
        records = [r for r in self._read_all() if r.get("event") == event]
        return records[-1] if records else None
