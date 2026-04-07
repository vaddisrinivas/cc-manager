"""cc-manager hook dispatcher — installed to ~/.cc-manager/hook.py."""
from __future__ import annotations

import importlib
import json
import sys
import threading
from pathlib import Path


def _run_with_timeout(fn, args, timeout_s: float):
    result = {}
    exc = []

    def target():
        try:
            r = fn(*args)
            if isinstance(r, dict):
                result.update(r)
        except Exception as e:
            exc.append(e)

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout=timeout_s)
    return result


HANDLER_MAP = {
    "SessionStart": "cc_manager.handlers.session_start",
    "SessionEnd": "cc_manager.handlers.session_end",
    "Stop": "cc_manager.handlers.stop",
    "PostToolUse": "cc_manager.handlers.post_tool_use",
    "PreCompact": "cc_manager.handlers.pre_compact",
}


def dispatch(event_name: str, payload: dict) -> dict:
    """Dispatch to the matching handler and return merged output."""
    module_path = HANDLER_MAP.get(event_name)
    if not module_path:
        return {}

    try:
        from cc_manager.context import get_ctx
        ctx = get_ctx()
        module = importlib.import_module(module_path)
        handle_fn = getattr(module, "handle", None)
        if handle_fn is None:
            return {}
        timeout_ms = getattr(module, "TIMEOUT_MS", 5000)
        result = _run_with_timeout(handle_fn, (payload, ctx), timeout_ms / 1000.0)
        return result or {}
    except Exception:
        return {}


def main():
    if len(sys.argv) < 2:
        print("{}")
        sys.exit(0)

    event_name = sys.argv[1]
    try:
        payload_text = sys.stdin.read()
        payload = json.loads(payload_text) if payload_text.strip() else {}
    except Exception:
        payload = {}

    try:
        output = dispatch(event_name, payload)
    except Exception:
        output = {}

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
