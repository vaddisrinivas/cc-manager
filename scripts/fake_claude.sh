#!/usr/bin/env bash
# fake_claude.sh — simulates a complete Claude Code session lifecycle.
#
# Claude Code fires hooks by calling the configured command with a JSON
# payload on stdin. This script does exactly that using the hook.py
# that `ccm init` installs to ~/.cc-manager/hook.py.
#
# Usage: bash scripts/fake_claude.sh [session_id]
#   SESSION_ID defaults to "fake-session-001"
#
# Outputs: prints each hook response (JSON) and exits 0 on success.

set -euo pipefail

SESSION="${1:-fake-session-001}"
HOOK="${HOME}/.cc-manager/hook.py"

if [[ ! -f "$HOOK" ]]; then
    echo "ERROR: $HOOK not found — run 'ccm init' first" >&2
    exit 1
fi

fire() {
    local event="$1"
    local payload="$2"
    echo "[fake-claude] firing $event ..."
    local response
    response=$(echo "$payload" | python3 "$HOOK" "$event" 2>&1)
    echo "[fake-claude] $event response: $response"
}

# ── 1. Session starts ─────────────────────────────────────────────────────────
fire "SessionStart" "$(cat <<EOF
{
  "session_id": "$SESSION",
  "sessionId":  "$SESSION",
  "cwd":        "/tmp/fake-project",
  "model":      "claude-sonnet-4-6"
}
EOF
)"

# ── 2. Simulate a few tool uses ───────────────────────────────────────────────
fire "PostToolUse" "$(cat <<EOF
{
  "session_id":    "$SESSION",
  "tool_name":     "Bash",
  "tool_input":    {"command": "ls /tmp"},
  "tool_response": "file1\nfile2\nfile3",
  "cost_usd":      0.005
}
EOF
)"

fire "PostToolUse" "$(cat <<EOF
{
  "session_id":    "$SESSION",
  "tool_name":     "Read",
  "tool_input":    {"file_path": "/tmp/README.md"},
  "tool_response": "# Fake project",
  "cost_usd":      0.002
}
EOF
)"

# ── 3. Pre-compact fires (context window pressure) ────────────────────────────
fire "PreCompact" "$(cat <<EOF
{
  "session_id":     "$SESSION",
  "trigger":        "manual",
  "context_tokens": 180000
}
EOF
)"

# ── 4. Session ends ───────────────────────────────────────────────────────────
fire "SessionEnd" "$(cat <<EOF
{
  "session_id": "$SESSION",
  "sessionId":  "$SESSION",
  "model":      "claude-sonnet-4-6",
  "usage": {
    "input_tokens":             45000,
    "output_tokens":            8500,
    "cache_read_input_tokens":  12000
  },
  "duration_min": 22
}
EOF
)"

# ── 5. Stop fires after session ends ─────────────────────────────────────────
fire "Stop" "$(cat <<EOF
{
  "session_id": "$SESSION",
  "sessionId":  "$SESSION",
  "total_cost": 0.045
}
EOF
)"

echo "[fake-claude] session $SESSION complete"
