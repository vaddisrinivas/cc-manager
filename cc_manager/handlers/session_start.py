"""SessionStart handler."""
from __future__ import annotations
EVENT = "SessionStart"
TIMEOUT_MS = 5000

def handle(payload: dict, ctx) -> dict:
    session_id = payload.get("session_id", payload.get("sessionId", "unknown"))
    cwd = payload.get("cwd", "")
    model = payload.get("model", "unknown")
    ctx.store.append("session_start", session=session_id, cwd=cwd, model=model)

    # Check installed tools
    missing = []
    for name, info in ctx.installed.get("tools", {}).items():
        reg = next((t for t in ctx.registry if t["name"] == name), None)
        if not reg:
            continue
        detect = reg.get("detect", {})
        if detect.get("type") == "binary":
            from cc_manager.context import run_cmd
            rc, _ = run_cmd(detect.get("command", ""), timeout=3)
            if rc != 0:
                missing.append(name)

    if missing:
        return {"additionalContext": f"cc-manager: {', '.join(missing)} not found in PATH"}
    return {}
