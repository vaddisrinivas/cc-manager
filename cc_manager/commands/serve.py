"""cc-manager serve command — local JSON API server."""
from __future__ import annotations

import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from pathlib import Path

import typer
from rich.console import Console

import cc_manager.context as ctx_mod
import cc_manager.settings as settings_mod
from cc_manager import __version__
from cc_manager.commands.install import (
    AlreadyInstalledError,
    InstallError,
    ToolNotFoundError,
    install_tool,
)
from cc_manager.context import CONFIG_PATH, get_ctx, parse_duration

try:
    import tomli_w
except ImportError:
    tomli_w = None  # type: ignore[assignment]

console = Console()


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class CCManagerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the cc-manager JSON API."""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Suppress default access log to stderr."""

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/api/status":
            self._handle_status()
        elif path == "/api/tools":
            self._handle_tools()
        elif path == "/api/sessions":
            self._handle_sessions(params)
        elif path == "/api/analyze":
            self._handle_analyze(params)
        elif path == "/api/events":
            self._handle_events(params)
        elif path == "/api/doctor":
            self._handle_doctor()
        elif path == "/api/recommend":
            self._handle_recommend()
        elif path == "/api/registry":
            self._handle_registry(params)
        else:
            self._json_response({"error": "not found"}, 404)

    # ------------------------------------------------------------------
    # Core helper
    # ------------------------------------------------------------------

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}

        if path == "/api/install":
            self._handle_install(body)
        elif path == "/api/remove":
            self._handle_remove(body)
        elif path == "/api/doctor/run":
            self._handle_doctor_run()
        elif path == "/api/module":
            self._handle_module(body)
        else:
            self._json_response({"error": "not found"}, 404)

    def _json_response(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------------
    # Route handlers
    # ------------------------------------------------------------------

    def _handle_status(self) -> None:
        ctx = get_ctx()

        # Build installed_tools list from ctx.installed["tools"]
        tools_dict = ctx.installed.get("tools", {})
        installed_tools = [
            {
                "name": name,
                "version": info.get("version", "unknown"),
                "method": info.get("method", "unknown"),
                "status": "ok",
            }
            for name, info in tools_dict.items()
        ]

        # Count hooks from settings
        hooks_count = _count_hooks(ctx.settings)

        self._json_response(
            {
                "version": __version__,
                "installed_tools": installed_tools,
                "hooks_registered": hooks_count,
                "config_path": str(CONFIG_PATH).replace(str(Path.home()), "~"),
            }
        )

    def _handle_tools(self) -> None:
        ctx = get_ctx()
        tools_dict = ctx.installed.get("tools", {})
        tools = [
            {
                "name": name,
                "version": info.get("version", "unknown"),
                "method": info.get("method", "unknown"),
                "installed_at": info.get("installed_at", ""),
                "pinned": info.get("pinned", False),
            }
            for name, info in tools_dict.items()
        ]
        self._json_response({"tools": tools})

    def _handle_sessions(self, params: dict) -> None:
        ctx = get_ctx()
        since_str = _first(params, "since", "7d")
        since_dt = _since_datetime(since_str)
        sessions = ctx.store.sessions(since=since_dt)
        self._json_response({"sessions": sessions})

    def _handle_analyze(self, params: dict) -> None:
        ctx = get_ctx()
        period = _first(params, "period", "7d")
        since_dt = _since_datetime(period)

        sessions = ctx.store.sessions(since=since_dt)
        compaction_events = len(ctx.store.query(event="compaction", since=since_dt))

        total_sessions = len(sessions)
        total_input = sum(int(s.get("input_tokens") or 0) for s in sessions)
        total_output = sum(int(s.get("output_tokens") or 0) for s in sessions)
        total_cache = sum(int(s.get("cache_read") or 0) for s in sessions)
        total_cost = sum(float(s.get("cost_usd") or 0) for s in sessions)
        total_dur = sum(float(s.get("duration_min") or 0) for s in sessions)

        period_days = parse_duration(period).total_seconds() / 86400
        sessions_per_day = round(total_sessions / period_days, 1) if period_days else 0
        avg_duration = round(total_dur / total_sessions, 1) if total_sessions else 0
        avg_tokens = (
            round((total_input + total_output) / total_sessions)
            if total_sessions else 0
        )

        # Model breakdown as fractions
        model_counts: dict[str, int] = {}
        for s in sessions:
            m = s.get("model") or "unknown"
            model_counts[m] = model_counts.get(m, 0) + 1
        model_breakdown = (
            {m: round(c / total_sessions, 4) for m, c in model_counts.items()}
            if total_sessions else {}
        )

        self._json_response(
            {
                "period": period,
                "total_sessions": total_sessions,
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_cache_read": total_cache,
                "total_cost_usd": round(total_cost, 4),
                "sessions_per_day": sessions_per_day,
                "avg_duration_min": avg_duration,
                "avg_tokens_per_session": avg_tokens,
                "compaction_events": compaction_events,
                "model_breakdown": model_breakdown,
            }
        )

    def _handle_events(self, params: dict) -> None:
        ctx = get_ctx()
        event_filter = _first(params, "event", None)
        since_str = _first(params, "since", None)
        try:
            limit = int(_first(params, "limit", "100"))
        except (TypeError, ValueError):
            limit = 100

        since_dt = _since_datetime(since_str) if since_str else None
        events = ctx.store.query(event=event_filter, since=since_dt, limit=limit)
        self._json_response({"events": events})

    def _handle_doctor(self) -> None:
        ctx = get_ctx()
        checks = []

        # 1. rtk check
        checks.append(_check_rtk(ctx))

        # 2. settings.json hooks check
        checks.append(_check_settings_json(ctx))

        # 3. config.toml check
        checks.append(_check_config_toml(ctx))

        # 4. store writable
        checks.append(_check_store_writable(ctx))

        # 5. python version
        checks.append(_check_python_version())

        summary = {
            "ok": sum(1 for c in checks if c["status"] == "ok"),
            "warn": sum(1 for c in checks if c["status"] == "warn"),
            "fail": sum(1 for c in checks if c["status"] == "fail"),
        }
        self._json_response({"checks": checks, "summary": summary})

    def _handle_recommend(self) -> None:
        ctx = get_ctx()
        recommendations = []

        tools_dict = ctx.installed.get("tools", {})
        mcp_tools = [
            name for name, info in tools_dict.items()
            if info.get("method") == "mcp"
        ]

        if not mcp_tools:
            recommendations.append(
                {
                    "rule": "no_mcp_servers",
                    "message": (
                        "No MCP servers installed. "
                        "Consider context7 for version-specific docs."
                    ),
                    "install_cmd": "ccm install context7",
                    "tool": "context7",
                }
            )

        self._json_response({"recommendations": recommendations})

    def _handle_registry(self, params: dict) -> None:
        ctx = get_ctx()
        tier_filter = _first(params, "tier", None)
        installed_filter = _first(params, "installed", None)

        tools_dict = ctx.installed.get("tools", {})
        installed_names = set(tools_dict.keys())

        tools = list(ctx.registry)

        if tier_filter:
            tools = [t for t in tools if t.get("tier") == tier_filter]

        if installed_filter is not None:
            want_installed = installed_filter.lower() not in ("false", "0", "no")
            if want_installed:
                tools = [t for t in tools if t.get("name") in installed_names]
            else:
                tools = [t for t in tools if t.get("name") not in installed_names]

        self._json_response({"tools": tools})

    def _handle_install(self, body: dict) -> None:
        name = body.get("tool", "")
        if not name:
            self._json_response({"ok": False, "error": "missing tool name"}, 400)
            return
        try:
            install_tool(name)
            self._json_response({"ok": True, "tool": name, "message": f"Installed {name}"})
        except AlreadyInstalledError:
            self._json_response({"ok": False, "error": "already installed"})
        except (ToolNotFoundError, InstallError) as exc:
            self._json_response({"ok": False, "error": str(exc)})
        except Exception as exc:
            self._json_response({"ok": False, "error": str(exc)})

    def _handle_remove(self, body: dict) -> None:
        ctx = get_ctx()
        name = body.get("tool", "")
        if not name:
            self._json_response({"ok": False, "error": "missing tool name"}, 400)
            return
        installed = ctx.installed.get("tools", {})
        if name not in installed:
            self._json_response({"ok": False, "error": f"{name} is not installed"})
            return
        info = installed[name]
        method = info.get("method", "")
        if method == "mcp":
            try:
                settings_mod.remove_mcp(name)
            except Exception:
                pass
        del installed[name]
        path = ctx_mod.REGISTRY_PATH
        path.write_text(json.dumps(ctx.installed, indent=2), encoding="utf-8")
        ctx.store.append("uninstall", tool=name)
        self._json_response({"ok": True, "tool": name, "message": f"Removed {name}"})

    def _handle_doctor_run(self) -> None:
        self._handle_doctor()

    def _handle_module(self, body: dict) -> None:
        ctx = get_ctx()
        module_name = body.get("module", "")
        enabled = body.get("enabled", True)
        if not module_name:
            self._json_response({"ok": False, "error": "missing module name"}, 400)
            return
        config = ctx.config or {}
        modules = config.setdefault("modules", {})
        modules.setdefault(module_name, {})["enabled"] = enabled
        try:
            if tomli_w is None:
                raise RuntimeError("tomli_w is not installed")
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_bytes(tomli_w.dumps(config).encode())
        except Exception as exc:
            self._json_response({"ok": False, "error": str(exc)})
            return
        self._json_response({"ok": True, "module": module_name, "enabled": enabled})


# ---------------------------------------------------------------------------
# Doctor check helpers
# ---------------------------------------------------------------------------

def _check_rtk(ctx: Any) -> dict:
    """Check if rtk is installed and runnable."""
    tools_dict = ctx.installed.get("tools", {})
    if "rtk" not in tools_dict:
        return {"name": "rtk", "status": "warn", "detail": "not installed"}
    try:
        result = subprocess.run(
            ["rtk", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            version = result.stdout.strip() or tools_dict["rtk"].get("version", "unknown")
            return {"name": "rtk", "status": "ok", "detail": version}
        return {"name": "rtk", "status": "warn", "detail": "not runnable"}
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        installed_ver = tools_dict.get("rtk", {}).get("version", "unknown")
        return {"name": "rtk", "status": "warn", "detail": f"not on PATH (installed: {installed_ver})"}


def _check_settings_json(ctx: Any) -> dict:
    """Check settings.json has cc-manager hooks."""
    hooks = ctx.settings.get("hooks", {})
    hook_count = _count_hooks(ctx.settings)
    if hook_count > 0:
        return {"name": "settings_json", "status": "ok", "detail": f"{hook_count} cc-manager hooks"}
    return {"name": "settings_json", "status": "warn", "detail": "no hooks registered"}


def _check_config_toml(ctx: Any) -> dict:
    """Check config TOML is loaded."""
    if ctx.config is not None:
        return {"name": "config_toml", "status": "ok", "detail": None}
    return {"name": "config_toml", "status": "warn", "detail": "config not loaded"}


def _check_store_writable(ctx: Any) -> dict:
    """Check that the event store path is writable."""
    try:
        store = ctx.store
        store_path = store.path
        store_path.parent.mkdir(parents=True, exist_ok=True)
        # Try opening for append
        with open(store_path, "a"):
            pass
        return {"name": "store_writable", "status": "ok", "detail": None}
    except Exception as exc:
        return {"name": "store_writable", "status": "fail", "detail": str(exc)}


def _check_python_version() -> dict:
    """Check Python version is 3.11+."""
    v = sys.version_info
    ver_str = f"{v.major}.{v.minor}.{v.micro}"
    if v >= (3, 11):
        return {"name": "python_version", "status": "ok", "detail": ver_str}
    return {
        "name": "python_version",
        "status": "warn",
        "detail": f"{ver_str} (3.11+ recommended)",
    }


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _first(params: dict, key: str, default: Any) -> Any:
    """Return first value of a query-string param, or default."""
    vals = params.get(key)
    if vals:
        return vals[0]
    return default


def _since_datetime(duration_str: str):
    """Convert a duration string like '7d' to an absolute datetime."""
    from datetime import datetime, timezone
    delta = parse_duration(duration_str)
    return datetime.now(timezone.utc) - delta


def _count_hooks(settings: dict) -> int:
    """Count total hook entries across all hook categories in settings."""
    hooks_section = settings.get("hooks", {})
    total = 0
    for _event, hook_list in hooks_section.items():
        if isinstance(hook_list, list):
            for entry in hook_list:
                if isinstance(entry, dict):
                    inner = entry.get("hooks", [])
                    total += len(inner) if isinstance(inner, list) else 1
    return total


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def run(port: int = typer.Option(9847, "--port", help="Port to serve on")) -> None:
    """Start local JSON API server."""
    server = HTTPServer(("127.0.0.1", port), CCManagerHandler)
    console.print(
        f"[green]cc-manager API running at http://localhost:{port}/api/[/green]"
    )
    console.print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
