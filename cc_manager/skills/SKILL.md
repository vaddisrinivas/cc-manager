# cc-manager Skills

Available as `/cc-manager:<command>` slash commands.

## /cc-manager:status

Check your Claude Code ecosystem status: installed tools, hook registration, and last session summary.

**Usage:** `/cc-manager:status`

**What it does:**
- Lists all tools installed via cc-manager with version and install method
- Shows how many cc-manager hooks are registered in settings.json
- Displays last session token usage and cost

**Runs:** `ccm status` via Bash tool

**Example output:**
```
◉ CC-MANAGER  v0.1.0  Claude Code Ecosystem Controller
⚡ INSTALLED TOOLS
  ✓  rtk    latest   binary   2026-04-01T10:00:00
⚡ HOOKS
  ✓  5 cc-manager hooks registered in settings.json
⚡ LAST SESSION
  12K input · 3K output · 45K cache · $0.0012 · 8 min
```

---

## /cc-manager:install

Install a tool from the cc-manager registry.

**Usage:** `/cc-manager:install <tool-name>`

**What it does:**
- Looks up `<tool-name>` in the registry
- Runs the install command (brew, npm, cargo, etc.) or registers an MCP server
- Records the install in `~/.cc-manager/registry/installed.json`

**Runs:** `ccm install <tool-name>` via Bash tool

**Example:**
```
/cc-manager:install rtk
/cc-manager:install context7
```

---

## /cc-manager:doctor

Run a full health check of the cc-manager installation.

**Usage:** `/cc-manager:doctor`

**What it does:**
- Verifies all expected hook events are registered in settings.json
- Checks that `~/.cc-manager/hook.py` exists and is executable
- Validates config file at `~/.cc-manager/cc-manager.toml`
- Reports any issues with actionable fix commands

**Runs:** `ccm doctor` via Bash tool

**Example output:**
```
◉ CC-MANAGER DOCTOR
  ✓  hook.py present
  ✓  5/5 hook events registered
  ✓  config valid
  ✗  rtk not found in PATH — run: brew install rtk
```

---

## /cc-manager:analyze

Show token and cost analytics for the current or recent sessions.

**Usage:** `/cc-manager:analyze`

**What it does:**
- Reads session events from `~/.cc-manager/store/events.jsonl`
- Summarizes input/output/cache tokens and estimated cost
- Shows trends across recent sessions

**Runs:** `ccm analyze` via Bash tool

**Example output:**
```
◉ ANALYTICS  (last 7 days)
  Total sessions:   12
  Total tokens:     2.4M input · 340K output · 1.1M cache
  Estimated cost:   $0.87
  Avg per session:  200K tokens · $0.07
```

---

## /cc-manager:recommend

Get personalized tool recommendations based on your usage patterns.

**Usage:** `/cc-manager:recommend`

**What it does:**
- Analyzes your session history (tools used, hooks triggered, common tasks)
- Compares against the cc-manager registry
- Suggests tools you are not yet using that match your patterns

**Runs:** `ccm recommend` via Bash tool

**Example output:**
```
◉ RECOMMENDATIONS
  rtk     — Token optimizer (saves 60-90% on dev ops)  [not installed]
  context7 — Up-to-date library docs in-context        [not installed]
```

---

## /cc-manager:logs

Show recent cc-manager events from the session event store.

**Usage:** `/cc-manager:logs`

**What it does:**
- Tails the last N entries from `~/.cc-manager/store/events.jsonl`
- Shows event type, timestamp, and key fields (tokens, cost, tool name)
- Useful for verifying hooks are firing and data is being captured

**Runs:** `ccm logs` via Bash tool

**Example output:**
```
◉ RECENT EVENTS
  2026-04-07T09:12:01  session_start
  2026-04-07T09:12:45  post_tool_use   tool=Bash tokens=1240
  2026-04-07T09:18:30  session_end     input=45K output=8K cost=$0.0021
```
