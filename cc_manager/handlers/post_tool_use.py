"""PostToolUse handler."""
from __future__ import annotations
EVENT = "PostToolUse"
TIMEOUT_MS = 3000

def handle(payload: dict, ctx) -> dict:
    session_id = payload.get("session_id", payload.get("sessionId", "unknown"))
    tool_name = payload.get("tool_name", payload.get("toolName", "unknown"))
    tool_input = payload.get("tool_input", payload.get("toolInput", {}))
    command = ""
    if tool_name == "Bash" and isinstance(tool_input, dict):
        command = tool_input.get("command", "")
    ctx.store.append("tool_use", session=session_id, tool=tool_name, command=command)
    return {}
