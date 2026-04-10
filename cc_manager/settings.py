"""Read/write ~/.claude/settings.json with fcntl locking and backups."""
from __future__ import annotations

import fcntl
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from cc_manager.paths import SETTINGS_PATH, BACKUPS_DIR, LOCK_PATH

_LOCK_TIMEOUT = 5.0


# -- Locking ----------------------------------------------------------------

def _acquire_lock(lock_file, exclusive: bool = False, timeout: float = _LOCK_TIMEOUT) -> None:
    flag = (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(lock_file.fileno(), flag)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Could not acquire settings lock after {timeout}s")
            time.sleep(0.05)


# -- Read / Write -----------------------------------------------------------

def read() -> dict:
    """Read settings.json with a shared lock. Returns {} if missing."""
    if not SETTINGS_PATH.exists():
        return {}
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_PATH, "a+") as lf:
        _acquire_lock(lf, exclusive=False)
        try:
            text = SETTINGS_PATH.read_text(encoding="utf-8")
            return json.loads(text) if text.strip() else {}
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def write(data: dict, backup: bool = True) -> None:
    """Write settings.json with an exclusive lock. Optionally backup first."""
    if backup and SETTINGS_PATH.exists():
        backup_create()
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_PATH, "a+") as lf:
        _acquire_lock(lf, exclusive=True)
        try:
            SETTINGS_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


# -- Backups ----------------------------------------------------------------

def backup_create() -> Path:
    """Copy settings.json to backups/ with timestamp suffix."""
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    dest = BACKUPS_DIR / f"settings.json.{ts}"
    shutil.copy2(SETTINGS_PATH, dest)
    return dest


def backup_list() -> list[Path]:
    """Return backup paths sorted oldest-first."""
    if not BACKUPS_DIR.exists():
        return []
    return sorted(BACKUPS_DIR.glob("settings.json.*"))


# -- Merge / Remove helpers -------------------------------------------------

def merge_hooks(hooks: dict) -> None:
    """Add hooks to settings['hooks'] without touching others."""
    data = read()
    data.setdefault("hooks", {}).update(hooks)
    write(data, backup=False)


def remove_hooks() -> None:
    """Remove hooks where command path contains '.cc-manager'."""
    data = read()
    hooks = data.get("hooks", {})
    to_delete = []
    for event_name, hook_list in hooks.items():
        filtered = []
        for entry in hook_list:
            inner = [h for h in entry.get("hooks", [])
                     if ".cc-manager" not in h.get("command", "")]
            if inner:
                filtered.append({**entry, "hooks": inner})
        if filtered:
            hooks[event_name] = filtered
        else:
            to_delete.append(event_name)
    for k in to_delete:
        del hooks[k]
    data["hooks"] = hooks
    write(data, backup=False)


def merge_mcp(name: str, config: dict) -> None:
    """Add or update an MCP server entry."""
    data = read()
    data.setdefault("mcpServers", {})[name] = config
    write(data, backup=False)


def remove_mcp(name: str) -> None:
    """Remove an MCP server entry."""
    data = read()
    data.get("mcpServers", {}).pop(name, None)
    write(data, backup=False)
