"""cc-manager settings — read/write ~/.claude/settings.json with locking."""
from __future__ import annotations

import fcntl
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

# These are module-level so tests can monkeypatch them
from cc_manager.context import SETTINGS_PATH, MANAGER_DIR, BACKUPS_DIR

LOCK_PATH = MANAGER_DIR / ".settings.lock"


def _ensure_backups_dir() -> None:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


def read() -> dict:
    """Read settings.json with a shared (read) lock. Returns {} if missing."""
    if not SETTINGS_PATH.exists():
        return {}
    lock_path = LOCK_PATH
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_SH)
        try:
            text = SETTINGS_PATH.read_text(encoding="utf-8")
            if not text.strip():
                return {}
            return json.loads(text)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def write(data: dict, backup: bool = True) -> None:
    """Write settings.json with an exclusive lock. Optionally backup first."""
    if backup and SETTINGS_PATH.exists():
        backup_create()
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_path = LOCK_PATH
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def backup_create() -> Path:
    """Copy current settings.json to backups/settings.json.<YYYYMMDD-HHMMSS-ffffff>."""
    _ensure_backups_dir()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    dest = BACKUPS_DIR / f"settings.json.{ts}"
    if SETTINGS_PATH.exists():
        shutil.copy2(SETTINGS_PATH, dest)
    else:
        dest.write_text("{}", encoding="utf-8")
    return dest


def backup_list() -> list[Path]:
    """Return list of backup paths sorted by name (oldest first)."""
    _ensure_backups_dir()
    backups = sorted(BACKUPS_DIR.glob("settings.json.*"))
    return backups


def backup_restore(timestamp: str) -> None:
    """Restore backup with given timestamp. Backs up current first."""
    backup_create()
    src = BACKUPS_DIR / f"settings.json.{timestamp}"
    if not src.exists():
        raise FileNotFoundError(f"No backup found: {src}")
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, SETTINGS_PATH)


def merge_hooks(hooks: dict) -> None:
    """Add hooks to settings['hooks'] without touching others."""
    data = read()
    existing = data.setdefault("hooks", {})
    existing.update(hooks)
    write(data, backup=False)


def remove_hooks() -> None:
    """Remove hooks where command path contains '.cc-manager'."""
    data = read()
    hooks = data.get("hooks", {})
    keys_to_delete = []
    for event_name, hook_list in hooks.items():
        filtered = []
        for entry in hook_list:
            # entry is like {"matcher": "", "hooks": [{"type": "command", "command": "..."}]}
            inner_hooks = entry.get("hooks", [])
            inner_filtered = [
                h for h in inner_hooks
                if ".cc-manager" not in h.get("command", "")
            ]
            if inner_filtered:
                filtered.append({**entry, "hooks": inner_filtered})
        if filtered:
            hooks[event_name] = filtered
        else:
            keys_to_delete.append(event_name)
    for k in keys_to_delete:
        del hooks[k]
    data["hooks"] = hooks
    write(data, backup=False)


def merge_mcp(name: str, config: dict) -> None:
    """Add or update an MCP server entry in settings['mcpServers']."""
    data = read()
    servers = data.setdefault("mcpServers", {})
    servers[name] = config
    write(data, backup=False)


def remove_mcp(name: str) -> None:
    """Remove an MCP server entry from settings['mcpServers']."""
    data = read()
    servers = data.get("mcpServers", {})
    servers.pop(name, None)
    if "mcpServers" in data:
        data["mcpServers"] = servers
    write(data, backup=False)
