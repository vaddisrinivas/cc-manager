"""PreCompact handler."""
from __future__ import annotations
EVENT = "PreCompact"
TIMEOUT_MS = 3000

def handle(payload: dict, ctx) -> dict:
    session_id = payload.get("session_id", payload.get("sessionId", "unknown"))
    trigger = payload.get("trigger", "auto")
    tokens_at_compact = payload.get("tokens_at_compact", payload.get("tokensAtCompact", 0))
    ctx.store.append("compact", session=session_id, trigger=trigger, tokens_at_compact=tokens_at_compact)
    return {}
