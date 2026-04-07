"""cc-manager context — paths, singleton context, helpers."""
from __future__ import annotations

import importlib.resources
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cc_manager.store import Store

# ---------------------------------------------------------------------------
# Canonical paths
# ---------------------------------------------------------------------------
CLAUDE_DIR = Path.home() / ".claude"
MANAGER_DIR = Path.home() / ".cc-manager"
SETTINGS_PATH = CLAUDE_DIR / "settings.json"
CONFIG_PATH = MANAGER_DIR / "cc-manager.toml"
STORE_PATH = MANAGER_DIR / "store" / "events.jsonl"
REGISTRY_PATH = MANAGER_DIR / "registry" / "installed.json"
BACKUPS_DIR = MANAGER_DIR / "backups"
STATE_PATH = MANAGER_DIR / "state" / "state.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_duration(spec: str) -> timedelta:
    """Parse a duration string like '7d', '30d', '24h', '1h' into a timedelta."""
    spec = spec.strip()
    if spec.endswith("d"):
        return timedelta(days=int(spec[:-1]))
    if spec.endswith("h"):
        return timedelta(hours=int(spec[:-1]))
    if spec.endswith("m"):
        return timedelta(minutes=int(spec[:-1]))
    raise ValueError(f"Unknown duration format: {spec!r}. Use e.g. '7d', '24h'.")


def run_cmd(cmd: str, timeout: int = 30) -> tuple[int, str]:
    """Run a shell command and return (returncode, combined_output)."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode, output.strip()
    except subprocess.TimeoutExpired:
        return 1, f"Command timed out after {timeout}s"
    except Exception as e:
        return 1, str(e)


def load_registry() -> list:
    """Load bundled registry/tools.json via importlib.resources."""
    try:
        # Try importlib.resources (works when installed as a package)
        import importlib.resources as pkg_resources
        try:
            ref = pkg_resources.files("registry").joinpath("tools.json")
            data = ref.read_text(encoding="utf-8")
            return json.loads(data)
        except (TypeError, AttributeError, ModuleNotFoundError):
            pass
    except Exception:
        pass

    # Fallback: look for registry/tools.json relative to this file or in common locations
    candidates = [
        Path(__file__).parent.parent / "registry" / "tools.json",
        MANAGER_DIR / "registry" / "tools.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))

    return []


def _load_settings() -> dict:
    """Load settings.json, returning {} if missing."""
    if not SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_installed() -> dict:
    """Load installed.json, returning default structure if missing."""
    if not REGISTRY_PATH.exists():
        return {"schema_version": 1, "tools": {}}
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": 1, "tools": {}}


def _load_config() -> dict:
    """Load cc-manager.toml, returning {} if missing."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        import tomllib  # Python 3.11+
        return tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Context class
# ---------------------------------------------------------------------------

class Context:
    """Runtime context for cc-manager commands."""

    def __init__(self):
        self.settings: dict = _load_settings()
        self.config: dict = _load_config()
        self.installed: dict = _load_installed()
        self.registry: list = load_registry()
        self.store: Store = Store(STORE_PATH)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_ctx: Context | None = None


def get_ctx() -> Context:
    """Return (or create) the global context singleton."""
    global _ctx
    if _ctx is None:
        _ctx = Context()
    return _ctx


def set_ctx(ctx: Context) -> None:
    """Set the module-level context (used by tests)."""
    global _ctx
    _ctx = ctx
