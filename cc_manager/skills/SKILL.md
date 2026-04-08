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

Install a tool from the cc-manager registry. Run the install command automatically — no need to copy-paste.

**Usage:** `/cc-manager:install <tool-name>`

**What it does:**
1. Runs `ccm info <tool-name>` to confirm the tool exists and show what will be installed
2. Runs `ccm install <tool-name>` — this executes the appropriate install command (cargo, npm, brew, MCP config, etc.)
3. Runs `ccm doctor` to verify the tool is detected correctly after install
4. Reports the result and any follow-up steps

**How it works:**
`ccm install` reads the install command directly from the registry entry — you never need to know the install method. The registry carries the correct command for each tool (cargo, npm, brew, MCP config, plugin, etc.) and `ccm install` runs it.

**Runs:** `ccm info <name> && ccm install <name> && ccm doctor` via Bash tool

**Example:**
```
/cc-manager:install rtk
/cc-manager:install context7
/cc-manager:install caveman
```

---

## /cc-manager:remove

Remove a tool installed via cc-manager.

**Usage:** `/cc-manager:remove <tool-name>`

**What it does:**
- Removes the tool entry from `~/.cc-manager/registry/installed.json`
- Cleans up any MCP server config in `~/.claude/settings.json`
- Does not uninstall system binaries (brew/npm/cargo managed separately)

**Runs:** `ccm remove <tool-name>` via Bash tool

**Example:**
```
/cc-manager:remove context7
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

Get tool recommendations derived from your actual session analytics.

**Usage:** `/cc-manager:recommend`

**What it does:**
- Runs `ccm analyze` to compute real usage stats (tokens, cost, compaction, model mix)
- Only surfaces a recommendation when the data justifies it — high token volume → RTK, high cost → cc-sentinel, Opus dominance → model warning, etc.
- Shows nothing if no sessions have been recorded yet

**Runs:** `ccm analyze && ccm recommend` via Bash tool

**Example output:**
```
◉ RECOMMENDATIONS  (from ccm analyze · last 7 days)
  rtk       avg 620K tokens/session — token filter saves 60-90%   ccm install rtk
  cc-sentinel  $3.40 spent this week — sentinel intercepts waste   ccm install cc-sentinel
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

---

## /cc-retrospect:cost

Show a cost breakdown from your most recent Claude Code session.

**Usage:** `/cc-retrospect:cost`

**Runs:** `cc-retrospect cost` via Bash tool

---

## /cc-retrospect:habits

Show habit patterns detected across your recent sessions.

**Usage:** `/cc-retrospect:habits`

**Runs:** `cc-retrospect habits` via Bash tool

---

## /cc-retrospect:health

Show a session health score — context pressure, compaction frequency, waste signals.

**Usage:** `/cc-retrospect:health`

**Runs:** `cc-retrospect health` via Bash tool

---

## /cc-retrospect:waste

Show real-time waste interception report — redundant tool calls, over-long prompts, unnecessary re-reads.

**Usage:** `/cc-retrospect:waste`

**Runs:** `cc-retrospect waste` via Bash tool

---

## /cc-retrospect:tips

Get actionable tips derived from your session patterns.

**Usage:** `/cc-retrospect:tips`

**Runs:** `cc-retrospect tips` via Bash tool

---

## /cc-retrospect:compare

Week-over-week comparison of token usage, cost, and session efficiency.

**Usage:** `/cc-retrospect:compare`

**Runs:** `cc-retrospect compare` via Bash tool

---

## /cc-retrospect:report

Full retrospective report — cost, habits, health, waste, and tips in one view.

**Usage:** `/cc-retrospect:report`

**Runs:** `cc-retrospect report` via Bash tool

---

## /cc-retrospect:hints

Show real-time pre-tool hints (fires before expensive tool calls to suggest cheaper alternatives).

**Usage:** `/cc-retrospect:hints`

**Runs:** `cc-retrospect hints` via Bash tool

---

## /cc-later:queue

Queue a task into LATER.md for dispatch near window expiry.

**Usage:** `/cc-later:queue <task description>`

**What it does:**
- Appends the task to `LATER.md` with priority and context
- cc-later dispatches queued tasks automatically as the context window fills

**Runs:** `cc-later queue "<task>"` via Bash tool

---

## /cc-later:list

Show all pending tasks in LATER.md.

**Usage:** `/cc-later:list`

**Runs:** `cc-later list` via Bash tool

---

## /cc-later:flush

Manually trigger dispatch of all LATER.md tasks now (without waiting for window pressure).

**Usage:** `/cc-later:flush`

**Runs:** `cc-later flush` via Bash tool
