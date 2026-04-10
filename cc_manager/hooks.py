"""Consolidated hook handlers — called by Claude Code via settings.json.

Entry point: `python -m cc_manager.hooks <event>`
Reads JSON payload from stdin, dispatches, writes JSON result to stdout.
"""
from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from cc_manager import installer, registry


def dispatch(event: str, payload: dict) -> dict:
    """Route event to handler, return output dict for Claude Code."""
    match event:
        case "SessionStart":
            return _session_start(payload)
        case "SessionEnd":
            return _session_end(payload)
        case "PostToolUse":
            return _post_tool_use(payload)
        case "Stop":
            return _stop(payload)
        case _:
            return {}


def _session_start(payload: dict) -> dict:
    """Check installed tools are still in PATH (parallel detection)."""
    installed = installer.load_installed()
    tools_map = registry.as_map()

    def _check(name: str) -> str | None:
        tool = tools_map.get(name)
        if not tool:
            return None
        cmd = tool.get("detect", {}).get("command", "")
        if not cmd:
            return None
        rc, _ = installer.run_cmd(cmd, timeout=3)
        return name if rc != 0 else None

    tool_names = list(installed.get("tools", {}).keys())
    missing: list[str] = []

    if tool_names:
        with ThreadPoolExecutor(max_workers=min(8, len(tool_names))) as pool:
            futures = {pool.submit(_check, n): n for n in tool_names}
            for fut in as_completed(futures):
                result = fut.result()
                if result:
                    missing.append(result)

    if missing:
        return {"additionalContext": f"cc-manager: {', '.join(missing)} not found in PATH"}
    return {}


def _session_end(payload: dict) -> dict:
    """No-op — analytics removed."""
    return {}


def _post_tool_use(payload: dict) -> dict:
    """No-op — analytics removed."""
    return {}


def _stop(payload: dict) -> dict:
    """No-op."""
    return {}


# -- CLI entry point --------------------------------------------------------

def main() -> None:
    """Read event + payload from stdin/argv, dispatch, write result to stdout."""
    if len(sys.argv) < 2:
        sys.stderr.write("usage: python -m cc_manager.hooks <event>\n")
        sys.exit(1)

    event = sys.argv[1]

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    try:
        result = dispatch(event, payload)
    except Exception as e:
        sys.stderr.write(f"[cc-manager] hook error ({event}): {e}\n")
        result = {}

    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
