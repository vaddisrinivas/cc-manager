"""cc-manager context — paths, singleton context, helpers."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from collections import defaultdict
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


def _parse_registry(raw: str) -> tuple[list, list]:
    """Parse registry JSON — supports both flat list and {profiles, tools} formats.
    Returns (tools, profiles)."""
    data = json.loads(raw)
    if isinstance(data, list):
        return data, []
    return data.get("tools", []), data.get("profiles", [])


def load_registry() -> list:
    """Load bundled registry/tools.json. Returns tools list."""
    tools, _ = _load_registry_raw()
    return tools


def load_profiles() -> list:
    """Load profiles: bundled registry profiles merged with local overrides.

    Local file: ~/.cc-manager/registry/profiles.json  (list of profile objects)
    Local profiles with the same name override bundled ones.
    Local-only profiles are appended at the end.
    This file survives ccm updates — it is never overwritten by the tool.
    """
    _, bundled = _load_registry_raw()
    local_path = MANAGER_DIR / "registry" / "profiles.json"
    if not local_path.exists():
        return bundled
    try:
        local = json.loads(local_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return bundled
    # merge: local overrides bundled by name, extras appended
    merged = {p["name"]: p for p in bundled}
    for p in local:
        if isinstance(p, dict) and p.get("name"):
            merged[p["name"]] = p
    return list(merged.values())


def _load_registry_raw() -> tuple[list, list]:
    """Load registry from disk/package, returning (tools, profiles)."""
    try:
        import importlib.resources as pkg_resources
        try:
            ref = pkg_resources.files("registry").joinpath("tools.json")
            return _parse_registry(ref.read_text(encoding="utf-8"))
        except (TypeError, AttributeError, ModuleNotFoundError):
            pass
    except Exception:
        pass

    candidates = [
        Path(__file__).parent.parent / "registry" / "tools.json",
        MANAGER_DIR / "registry" / "tools.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return _parse_registry(candidate.read_text(encoding="utf-8"))
    return [], []


def _load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_installed() -> dict:
    if not REGISTRY_PATH.exists():
        return {"schema_version": 1, "tools": {}}
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": 1, "tools": {}}


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        import tomllib
        return tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_installed(data: dict) -> None:
    """Persist installed.json to disk."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


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

    @property
    def registry_map(self) -> dict[str, dict]:
        """O(1) lookup by tool name. Derived from self.registry so stays in sync."""
        return {t["name"]: t for t in self.registry}

    # ── Installed registry mutations ───────────────────────────────────────────

    def record_installed(
        self,
        name: str,
        method: str,
        version: str = "latest",
    ) -> None:
        """Record a tool as installed, update in-memory state, and persist."""
        tools = self.installed.setdefault("tools", {})
        tools[name] = {
            "version": version,
            "method": method,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "pinned": False,
        }
        _write_installed(self.installed)

    def remove_installed(self, name: str) -> None:
        """Remove a tool from the installed registry and persist."""
        self.installed.get("tools", {}).pop(name, None)
        _write_installed(self.installed)


# ---------------------------------------------------------------------------
# Shared helpers (previously in utils.py)
# ---------------------------------------------------------------------------

def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n // 1_000}K"
    return str(n)


def dot_get(data: dict, key: str) -> Any:
    val: Any = data
    for part in key.split("."):
        val = val.get(part) if isinstance(val, dict) else None
    return val


def dot_set(data: dict, key: str, value: Any) -> dict:
    parts = key.split(".")
    d = data
    for part in parts[:-1]:
        d = d.setdefault(part, {})
    d[parts[-1]] = value
    return data


def daily_buckets(sessions: list[dict]) -> tuple[dict[str, int], dict[str, float]]:
    daily: dict[str, int] = defaultdict(int)
    costs: dict[str, float] = defaultdict(float)
    for s in sessions:
        day = (s.get("ts") or "")[:10]
        if day:
            daily[day] += s.get("input_tokens", 0) + s.get("output_tokens", 0)
            costs[day] += s.get("cost_usd", 0.0)
    return daily, costs


def run_health_checks(installed: dict, registry_map: dict, settings: dict) -> list[tuple[str, str, str]]:
    checks: list[tuple[str, str, str]] = []
    for name in installed:
        reg = registry_map.get(name)
        if reg is None:
            checks.append((name, "warn", "not in registry"))
            continue
        detect = reg.get("detect", {})
        cmd = detect.get("command", "")
        key = detect.get("settings_json_key", "")
        if cmd:
            rc, out = run_cmd(cmd, timeout=3)
            checks.append((name, "ok" if rc == 0 else "fail", out.strip()[:40]))
        elif key:
            checks.append((name, "ok" if dot_get(settings, key) is not None else "warn", key[:40]))
        else:
            checks.append((name, "ok", "configured"))
    return checks


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


def get_week_stats(store, days: int = 7) -> tuple[list[dict], float, int, int]:
    """Return (recent_sessions, week_cost, session_count, total_tokens) for the last N days.

    Single store query used by both `ccm` dashboard and `ccm status` so we don't
    read the events file twice.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent = store.query(event="session_end", since=cutoff, limit=1000)
    week_cost = sum(r.get("cost_usd", 0.0) for r in recent)
    week_sessions = len(recent)
    week_tokens = sum(r.get("input_tokens", 0) + r.get("output_tokens", 0) for r in recent)
    return recent, week_cost, week_sessions, week_tokens


def set_ctx(ctx: Context) -> None:
    """Set the module-level context (used by tests)."""
    global _ctx
    _ctx = ctx


def invalidate_ctx() -> None:
    """Invalidate the context singleton, forcing a fresh load on next get_ctx()."""
    global _ctx
    _ctx = None
