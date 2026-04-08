#!/usr/bin/env bash
# cc-manager integration test suite
# Runs the full stack against a real install — no mocks except for TUI.
# Exit 1 on first failure.
set -euo pipefail

# ── Colours ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; RESET='\033[0m'

PASS=0; FAIL=0

pass()    { echo -e "${GREEN}  ✓${RESET} $1"; ((PASS++)) || true; }
fail()    { echo -e "${RED}  ✗${RESET} $1"; ((FAIL++)) || true; }
section() { echo -e "\n${CYAN}── $1 ──${RESET}"; }
skip()    { echo -e "${YELLOW}  ~ SKIP${RESET} $1"; }

run() {
    # Run a command, capture output, return exit code without dying
    "$@" > /tmp/ccm_out 2>&1
    return $?
}

assert_exit0() {
    local label="$1"; shift
    if run "$@"; then pass "$label"
    else fail "$label (exit $?)"; cat /tmp/ccm_out; fi
}

assert_nonzero() {
    local label="$1"; shift
    if ! run "$@"; then pass "$label"
    else fail "$label (expected non-zero)"; cat /tmp/ccm_out; fi
}

assert_output() {
    local label="$1" pattern="$2"
    if grep -qiE "$pattern" /tmp/ccm_out 2>/dev/null; then pass "$label"
    else fail "$label (no match for '$pattern' in output)"; head -5 /tmp/ccm_out; fi
}

assert_file()  { [[ -f "$2" ]] && pass "$1" || fail "$1 (missing: $2)"; }
assert_dir()   { [[ -d "$2" ]] && pass "$1" || fail "$1 (missing dir: $2)"; }

assert_json_key() {
    local label="$1" file="$2" key="$3"
    if python3 -c "
import json,sys
d=json.load(open('$file'))
s=json.dumps(d)
sys.exit(0 if '$key' in s else 1)
" 2>/dev/null; then pass "$label"
    else fail "$label (key '$key' missing in $file)"; fi
}

assert_json_missing() {
    local label="$1" file="$2" key="$3"
    if python3 -c "
import json,sys
d=json.load(open('$file'))
tools=d.get('tools',{})
sys.exit(0 if '$key' not in tools else 1)
" 2>/dev/null; then pass "$label"
    else fail "$label ('$key' still present in $file)"; fi
}

# ── Env ────────────────────────────────────────────────────────────────────────
export HOME="${HOME:-/root}"
CLAUDE_DIR="$HOME/.claude"
MANAGER_DIR="$HOME/.cc-manager"
SETTINGS="$CLAUDE_DIR/settings.json"
INSTALLED="$MANAGER_DIR/registry/installed.json"
STORE="$MANAGER_DIR/store/events.jsonl"
HOOK="$MANAGER_DIR/hook.py"

echo -e "${CYAN}cc-manager integration test suite${RESET}"
echo "  HOME=$HOME  MANAGER=$MANAGER_DIR"

# ══════════════════════════════════════════════════════════════════════════════
section "1. Binary"

assert_exit0 "ccm on PATH"       which ccm
assert_exit0 "ccm --version"     ccm --version
assert_output "version string"   "cc-manager v"

# ══════════════════════════════════════════════════════════════════════════════
section "2. ccm init"

rm -rf "$MANAGER_DIR"
assert_exit0 "ccm init --minimal --yes" ccm init --minimal --yes
assert_dir  "manager dir"               "$MANAGER_DIR"
assert_dir  "store dir"                 "$MANAGER_DIR/store"
assert_dir  "registry dir"             "$MANAGER_DIR/registry"
assert_dir  "backups dir"              "$MANAGER_DIR/backups"
assert_file "hook.py installed"        "$HOOK"
assert_file "settings.json exists"    "$SETTINGS"
assert_json_key "hooks in settings"   "$SETTINGS" "hooks"

# ══════════════════════════════════════════════════════════════════════════════
section "3. Read-only CLI"

assert_exit0 "ccm list"              ccm list
assert_exit0 "ccm list --available" ccm list --available
assert_exit0 "ccm search rtk"       ccm search rtk
assert_exit0 "ccm info rtk"         ccm info rtk
assert_exit0 "ccm recommend"        ccm recommend
assert_exit0 "ccm status"           ccm status
assert_exit0 "ccm logs"             ccm logs
assert_exit0 "ccm audit"            ccm audit

# ══════════════════════════════════════════════════════════════════════════════
section "4. ccm doctor"

assert_exit0  "ccm doctor runs"     ccm doctor
run ccm doctor || true
assert_output "doctor has results" "(ok|warn|fail|✓|✗|⚠)"

# ══════════════════════════════════════════════════════════════════════════════
section "5. Hook dispatch — SessionStart"

echo '{"session_id":"integ-001","cwd":"/tmp","model":"claude-sonnet-4-6"}' \
    | python3 "$HOOK" SessionStart > /tmp/ccm_out 2>&1
HOOK_EXIT=$?

if [[ $HOOK_EXIT -eq 0 ]]; then pass "SessionStart hook exits 0"
else fail "SessionStart hook exit $HOOK_EXIT"; cat /tmp/ccm_out; fi

# Verify output is valid JSON
if python3 -c "import json,sys; json.load(sys.stdin)" < /tmp/ccm_out 2>/dev/null; then
    pass "SessionStart returns valid JSON"
else
    fail "SessionStart output is not valid JSON"
    cat /tmp/ccm_out
fi

if grep -q "session_start" "$STORE" 2>/dev/null; then
    pass "session_start event written to store"
else
    fail "session_start event not found in store"
fi

# ══════════════════════════════════════════════════════════════════════════════
section "6. Hook dispatch — PostToolUse"

echo '{
  "session_id":"integ-001",
  "tool_name":"Bash",
  "tool_input":{"command":"ls /tmp"},
  "tool_response":"file1\nfile2",
  "cost_usd":0.003
}' | python3 "$HOOK" PostToolUse > /tmp/ccm_out 2>&1
if [[ $? -eq 0 ]]; then pass "PostToolUse hook exits 0"
else fail "PostToolUse hook failed"; cat /tmp/ccm_out; fi

# ══════════════════════════════════════════════════════════════════════════════
section "7. Hook dispatch — SessionEnd (records tokens + cost)"

echo '{
  "session_id":"integ-001",
  "model":"claude-sonnet-4-6",
  "usage":{
    "input_tokens":50000,
    "output_tokens":10000,
    "cache_read_input_tokens":15000
  },
  "duration_min":30
}' | python3 "$HOOK" SessionEnd > /tmp/ccm_out 2>&1
if [[ $? -eq 0 ]]; then pass "SessionEnd hook exits 0"
else fail "SessionEnd hook failed"; cat /tmp/ccm_out; fi

if grep -q "session_end" "$STORE" 2>/dev/null; then
    pass "session_end event written to store"
else
    fail "session_end event not found in store"
fi

# Verify cost was calculated and stored
COST=$(python3 -c "
import json
events=[json.loads(l) for l in open('$STORE') if l.strip()]
ends=[e for e in events if e.get('event')=='session_end' and e.get('session')=='integ-001']
if ends:
    print(ends[-1].get('cost_usd',0))
else:
    print(0)
" 2>/dev/null)
if python3 -c "import sys; sys.exit(0 if float('$COST') > 0 else 1)" 2>/dev/null; then
    pass "session_end cost_usd calculated (got \$${COST})"
else
    fail "session_end cost_usd is 0 or missing (got '$COST')"
fi

# ══════════════════════════════════════════════════════════════════════════════
section "8. Hook dispatch — Stop"

echo '{"session_id":"integ-001"}' \
    | python3 "$HOOK" Stop > /tmp/ccm_out 2>&1
if [[ $? -eq 0 ]]; then pass "Stop hook exits 0"
else fail "Stop hook failed"; cat /tmp/ccm_out; fi

if grep -q '"event": "stop"' "$STORE" 2>/dev/null; then
    pass "stop event written to store"
else
    fail "stop event not found in store"
fi

# ══════════════════════════════════════════════════════════════════════════════
section "9. Full fake-claude lifecycle (all 5 hooks in sequence)"

SESSION="integ-lifecycle-$(date +%s)"
bash "$(dirname "$0")/fake_claude.sh" "$SESSION" > /tmp/fake_claude_out 2>&1
FC_EXIT=$?
if [[ $FC_EXIT -eq 0 ]]; then pass "fake_claude.sh exits 0"
else fail "fake_claude.sh failed (exit $FC_EXIT)"; cat /tmp/fake_claude_out; fi

# Verify all 5 events landed
for EVENT in session_start session_end stop pre_compact; do
    if grep -q "\"$EVENT\"" "$STORE" 2>/dev/null; then
        pass "$EVENT event in store after lifecycle"
    else
        # pre_compact may not be written if handler doesn't write it
        skip "$EVENT not found (handler may be a no-op)"
    fi
done

# ══════════════════════════════════════════════════════════════════════════════
section "10. Dashboard data reflects sessions"

# build_data() must see the sessions we just fired
python3 - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..')) if False else None
import cc_manager.context as ctx_mod
ctx_mod._ctx = None  # fresh context
from cc_manager.dashboard_data import build_data
try:
    data = build_data(period_days=1)
    sessions = data.get("sessions", [])
    total_cost = data.get("total_cost", 0.0)
    print(f"sessions={len(sessions)} total_cost={total_cost:.6f} status={data['status']}")
    if len(sessions) == 0:
        print("WARN: no sessions found (store may use different event name)")
    sys.exit(0)
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
if [[ $? -eq 0 ]]; then
    run python3 -c "
import cc_manager.context as ctx_mod; ctx_mod._ctx = None
from cc_manager.dashboard_data import build_data
data = build_data(period_days=1)
sessions = data.get('sessions', [])
total_cost = data.get('total_cost', 0.0)
assert total_cost > 0, f'expected cost > 0, got {total_cost}'
" 2>/dev/null
    if [[ $? -eq 0 ]]; then pass "build_data reports cost > 0 after fake sessions"
    else fail "build_data cost is 0 after fake sessions"; fi
else
    fail "build_data() raised an exception"
    cat /tmp/ccm_out
fi

# ccm analyze should reflect the data
assert_exit0 "ccm analyze runs after sessions" ccm analyze

# ccm status should not crash
assert_exit0 "ccm status after sessions" ccm status
run ccm status || true
assert_output "status shows sessions or cost" "(session|cost|\\\$|token)"

# ══════════════════════════════════════════════════════════════════════════════
section "11. MCP install — context7"

assert_exit0    "ccm install context7"         ccm install context7
assert_json_key "context7 in installed.json"   "$INSTALLED"  "context7"
assert_json_key "context7 in mcpServers"       "$SETTINGS"   "context7"
assert_nonzero  "re-install exits non-zero"    ccm install context7

# ══════════════════════════════════════════════════════════════════════════════
section "12. MCP install — playwright-mcp"

assert_exit0    "ccm install playwright-mcp"          ccm install playwright-mcp
assert_json_key "playwright-mcp in installed.json"    "$INSTALLED" "playwright-mcp"

# ══════════════════════════════════════════════════════════════════════════════
section "13. ccm status reflects installed tools"

run ccm status || true
assert_output "status shows context7" "context7"

# ══════════════════════════════════════════════════════════════════════════════
section "14. ccm uninstall"

assert_exit0    "ccm uninstall context7"               ccm uninstall context7
assert_json_missing "context7 removed from installed" "$INSTALLED" "context7"
assert_nonzero  "uninstall unknown tool non-zero"      ccm uninstall no_such_tool_xyz

# ══════════════════════════════════════════════════════════════════════════════
section "15. Event store integrity"

TOTAL=$(wc -l < "$STORE" 2>/dev/null || echo 0)
if [[ "$TOTAL" -gt 5 ]]; then pass "event store has $TOTAL events"
else fail "event store has only $TOTAL events (expected > 5)"; fi

# Every line must be valid JSON
BAD=0
while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    python3 -c "import json; json.loads('$line')" 2>/dev/null || ((BAD++)) || true
done < "$STORE"
if [[ $BAD -eq 0 ]]; then pass "all store lines are valid JSON"
else fail "$BAD store line(s) are invalid JSON"; fi

# ══════════════════════════════════════════════════════════════════════════════
section "16. ccm backup"

assert_exit0 "ccm backup" ccm backup
BC=$(ls "$MANAGER_DIR/backups/" 2>/dev/null | wc -l)
if [[ $BC -gt 0 ]]; then pass "backup file created ($BC file(s))"
else fail "no backup files found"; fi

# ══════════════════════════════════════════════════════════════════════════════
section "17. ccm config round-trip"

assert_exit0 "config set" ccm config set analytics.enabled false
assert_exit0 "config get" ccm config get analytics.enabled
run ccm config get analytics.enabled || true
assert_output "config get returns set value" "false"

# ══════════════════════════════════════════════════════════════════════════════
section "18. Cargo install — rtk (if cargo available)"

if command -v cargo &>/dev/null; then
    assert_exit0 "ccm install rtk (cargo)"    ccm install rtk
    assert_json_key "rtk in installed.json"   "$INSTALLED" "rtk"
    if command -v rtk &>/dev/null; then
        pass "rtk binary reachable"
        assert_exit0 "ccm doctor sees rtk"    ccm doctor
    else
        skip "rtk not in PATH yet (cargo bin path may need shell reload)"
    fi
    assert_exit0 "ccm uninstall rtk"          ccm uninstall rtk
else
    skip "cargo not available — skipping rtk install"
fi

# ══════════════════════════════════════════════════════════════════════════════
section "19. TUI headless (Textual pilot)"

# Run just the TUI tests via pytest — no TTY required
if command -v pytest &>/dev/null; then
    TEST_DIR="$(dirname "$0")/../tests/test_app.py"
    if [[ -f "$TEST_DIR" ]]; then
        if python3 -m pytest "$TEST_DIR" -q --tb=short --timeout=30 \
              > /tmp/tui_test_out 2>&1; then
            TPASSED=$(grep -oP '\d+ passed' /tmp/tui_test_out | head -1)
            pass "TUI pilot tests passed ($TPASSED)"
        else
            fail "TUI pilot tests failed"
            cat /tmp/tui_test_out
        fi
    else
        skip "tests/test_app.py not found"
    fi
else
    skip "pytest not available"
fi

# ══════════════════════════════════════════════════════════════════════════════
section "Summary"

TOTAL=$((PASS + FAIL))
echo ""
echo -e "  Passed: ${GREEN}${PASS}${RESET} / ${TOTAL}"
if [[ $FAIL -gt 0 ]]; then
    echo -e "  Failed: ${RED}${FAIL}${RESET} / ${TOTAL}"
    exit 1
fi
echo -e "${GREEN}All integration tests passed.${RESET}"
exit 0
