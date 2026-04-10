"""Canonical paths for cc-manager."""
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
SETTINGS_PATH = CLAUDE_DIR / "settings.json"
MANAGER_DIR = Path.home() / ".cc-manager"
INSTALLED_PATH = MANAGER_DIR / "installed.json"
BACKUPS_DIR = MANAGER_DIR / "backups"
LOCK_PATH = MANAGER_DIR / ".settings.lock"
