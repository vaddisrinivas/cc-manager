"""Stop handler."""
from __future__ import annotations
EVENT = "Stop"
TIMEOUT_MS = 3000

def handle(payload: dict, ctx) -> dict:
    session_id = payload.get("session_id", payload.get("sessionId", "unknown"))
    ctx.store.append("stop", session=session_id)
    return {}
