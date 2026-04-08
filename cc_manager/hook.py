"""cc-manager hook dispatcher — installed to ~/.cc-manager/hook.py."""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Any

from cc_manager.handlers import Handler

# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

_HANDLER_MODULES = {
    "SessionStart": "cc_manager.handlers.session_start",
    "SessionEnd":   "cc_manager.handlers.session_end",
    "Stop":         "cc_manager.handlers.stop",
    "PostToolUse":  "cc_manager.handlers.post_tool_use",
    "PreCompact":   "cc_manager.handlers.pre_compact",
}

# Loaded lazily on first dispatch, keyed by event name
_handlers: dict[str, Handler] = {}


def _load_handler(event_name: str) -> Handler | None:
    """Import and validate a handler, caching on success."""
    if event_name in _handlers:
        return _handlers[event_name]
    module_path = _HANDLER_MODULES.get(event_name)
    if not module_path:
        return None
    try:
        handler = Handler.from_module(module_path)
        _handlers[event_name] = handler
        return handler
    except (AttributeError, ImportError) as exc:
        # A broken handler should never crash a live session
        sys.stderr.write(f"[cc-manager] Failed to load handler for {event_name!r}: {exc}\n")
        return None


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_ERRORS_LOG = Path.home() / ".cc-manager" / "store" / "errors.log"


def _log_error(msg: str) -> None:
    try:
        _ERRORS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_ERRORS_LOG, "a") as f:
            from datetime import datetime, timezone
            ts = datetime.now(timezone.utc).isoformat()
            f.write(f"{ts} {msg}\n")
    except Exception:
        pass


def _run_with_timeout(fn, args: tuple, timeout_s: float) -> dict:
    result: dict = {}

    def target():
        try:
            r = fn(*args)
            if isinstance(r, dict):
                result.update(r)
        except Exception as exc:
            _log_error(f"handler {fn.__name__!r} raised: {exc}")

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout=timeout_s)
    return result


def dispatch(event_name: str, payload: dict) -> dict:
    """Dispatch to the matching handler and return merged output."""
    handler = _load_handler(event_name)
    if handler is None:
        return {}
    try:
        from cc_manager.context import get_ctx
        ctx = get_ctx()
        result = _run_with_timeout(handler.fn, (payload, ctx), handler.timeout_ms / 1000.0)
        return result or {}
    except Exception as exc:
        _log_error(f"dispatch {event_name!r} failed: {exc}")
        return {}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

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
