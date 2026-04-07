# cc-manager Technical Specification

A CLI tool that manages the Claude Code ecosystem: bundles cc-later as its core module, installs/removes external tools from a local registry, and provides a unified interface for configuration, diagnostics, and analytics.

**Version:** 0.1.0 (spec v2)
**Language:** Pure Python 3.10+, stdlib only
**Distribution:** `pipx install cc-manager` or `uv tool install cc-manager`

---

## Table of Contents

1. [Relationship to cc-later](#1-relationship-to-cc-later)
2. [Design Principles](#2-design-principles)
3. [v0.1 Scope](#3-v01-scope)
4. [Directory Structure](#4-directory-structure)
5. [CLI Command Reference](#5-cli-command-reference)
6. [Config Format](#6-config-format)
7. [Module System](#7-module-system)
8. [Tool Registry (tools.json)](#8-tool-registry-toolsjson)
9. [Dispatcher Architecture](#9-dispatcher-architecture)
10. [settings.json Management](#10-settingsjson-management)
11. [Migration from cc-later](#11-migration-from-cc-later)
12. [Implementation Plan](#12-implementation-plan)
13. [Appendices](#appendices)

---

## 1. Relationship to cc-later

cc-manager and cc-later are **separate projects**. cc-later is the existing Claude Code plugin that handles idle-capacity reclamation (LATER.md dispatch, window tracking, budget gates, compaction recovery, auto-resume, nudge, stats). cc-manager is a new project that:

- Bundles cc-later as its **built-in module** (vendored, not a pip dependency)
- Adds tool management (install/remove external tools from a registry)
- Adds init, doctor, backup, uninstall, and a unified CLI
- Replaces cc-later's plugin-based hook registration with global settings.json hooks via a single dispatcher

**What cc-later owns (unchanged):**
- later (LATER.md queue, task dispatch)
- compact (context recovery after compaction)
- resume (auto-resume limit-hit tasks)
- budget (weekly token budget enforcement)
- window (5-hour window lifecycle)
- stats (token analytics, cost tracking, configurable pricing)
- nudge (stale agent detection and restart)
- hooks infrastructure (handler.py, capture.py, compact.py)

**What cc-manager adds:**
- `init` command (environment detection, setup)
- `install` / `remove` commands (external tool management)
- `doctor` command (config validation, health checks)
- `backup` / `uninstall` commands
- `status` command (unified view of modules + tools)
- `module enable/disable/status` (toggle cc-later modules)
- `marketplace` (tools.json registry file, not a web service)
- `stats` (delegates to cc-later's stats module, surfaces pricing config)

---

## 2. Design Principles

1. **Own nothing, orchestrate everything.** cc-manager configures Claude Code. Every action maps to a file Claude Code already reads (settings.json, hooks, CLAUDE.md).

2. **Reversible.** `cc-manager uninstall` cleanly removes everything it added. No orphaned hooks, no corrupted settings.

3. **No runtime cost.** cc-manager is a CLI tool you run explicitly. It does not inject itself into Claude Code sessions. The cc-later modules it bundles run via Claude Code's hook system.

4. **Opinionated defaults, full override.** Ships a curated registry of recommended tools. Every choice is configurable.

5. **Pure Python, stdlib only.** Zero pip dependencies. Ships as a single package.

6. **Module isolation.** Each cc-later module runs independently in the dispatcher. If one crashes, others still fire. Timeouts are per-module. Doctor reports module health.

7. **Dry-run everywhere.** Every mutating command supports `--dry-run` to show what would change without writing anything.

---

## 3. v0.1 Scope

### Ships in v0.1

| Command | Description |
|---|---|
| `init` | Detect environment, create ~/.cc-manager/, merge hooks into settings.json |
| `status` | Unified view of all modules + installed tools |
| `module enable/disable/status` | Toggle cc-later modules individually |
| `install <tool>` | Install an external tool from the registry |
| `remove <tool>` | Remove an external tool, clean up settings.json entries |
| `list` | List tools from the registry (installed, available, by category) |
| `doctor` | Validate config, check hook conflicts, verify tool versions |
| `backup` | Snapshot settings.json and hooks before changes |
| `uninstall` | Clean removal of everything cc-manager added |
| `stats` | Delegates to cc-later's stats module; configurable pricing tables |
| `config` | Get/set config values, open editor |

### Deferred to v0.2+

- `upgrade` (self-upgrade with migration)
- `hooks list/check/repair` (standalone hook management CLI)
- Registry auto-update from GitHub
- Per-project module overrides
- Web dashboard integration

---

## 4. Directory Structure

### cc-manager home: `~/.cc-manager/`

```
~/.cc-manager/
├── cc-manager.toml               # Single config file (TOML)
├── dispatch.py                   # Hook entry point (delegates to modules)
├── registry/
│   ├── tools.json                # Tool catalog (ships with cc-manager, read-only)
│   └── installed.json            # Tracks what's installed, versions, install method
├── state/
│   ├── state.json                # Module state (window, budget, repos, stats)
│   └── run_log.jsonl             # Unified event log
├── backups/
│   ├── settings.json.<timestamp>
│   └── hooks.<timestamp>/
├── modules/                      # Vendored cc-later modules
│   ├── later/
│   │   ├── handler.py            # Stop hook handler
│   │   ├── capture.py            # UserPromptSubmit handler
│   │   └── SKILL.md
│   ├── compact/
│   │   └── handler.py            # SessionStart handler
│   ├── resume/                   # Logic integrated into later module
│   ├── budget/                   # Budget gate logic
│   ├── window/                   # Window state computation
│   ├── stats/
│   │   └── collector.py          # Token/cost aggregation
│   └── nudge/
│       └── handler.py            # Stale agent detection
├── results/                      # Dispatch result files
│   └── {repo}-{date}.json
└── worktrees/                    # Temporary git worktrees for dispatched agents
```

### What cc-manager writes to `~/.claude/`

cc-manager is a guest in Claude Code's directory. It writes to these specific locations:

| Path | What cc-manager does | Reversible |
|---|---|---|
| `settings.json` | Merges hook entries + MCP server configs | Yes (backup + targeted removal) |
| `CLAUDE.md` | Appends one line: `@cc-manager` | Yes (remove that line) |
| `cc-manager.md` | Instructions file referenced by CLAUDE.md | Yes (rm) |
| `skills/cc-manager/` | Skill definitions for built-in modules | Yes (rm -r) |

cc-manager **never** modifies:
- Non-cc-manager hook entries (rtk, plugins, user hooks)
- `enabledPlugins`, `allowedTools`, or other settings.json fields
- Plugin cache directories
- Project-level `.claude/` directories
- `history.jsonl`, `sessions/`, or any Claude Code internal state

---

## 5. CLI Command Reference

### `cc-manager init [--yes] [--minimal] [--dry-run]`

First-run setup. Idempotent (safe to re-run).

```
$ cc-manager init

cc-manager v0.1.0 — Claude Code ecosystem manager

Step 1/5: Detecting environment...
  Claude Code config: ~/.claude (found)
  settings.json: found (will merge, not overwrite)
  Existing hooks: rtk-rewrite.sh (PreToolUse)
  Python: 3.12.0
  cargo: found    go: found    npm: found    pip: found

Step 2/5: Backing up current config...
  settings.json -> ~/.cc-manager/backups/settings.json.20260406-120000

Step 3/5: Installing recommended tools...
  [1/10] rtk ............... v0.25.0 already installed
  [2/10] ccusage ........... not found. Install? [Y/n] y
         Installing: cargo install ccusage
  [3/10] context7 .......... MCP server (will add to settings.json)
  [4/10] playwright-mcp .... MCP server (will add to settings.json)
  [5/10] claude-squad ...... not found. Install? [Y/n] n
         Skipped.
  [6/10] agnix ............. not found. Install? [Y/n] y
         Installing: npm i -g @agent-sh/agnix
  [7/10] trail-of-bits ..... plugin (manual: claude plugin install trailofbits-skills)
  [8/10] claude-code-action  GitHub Action (manual: add to .github/workflows/)
  [9/10] code-review-graph . not found. Install? [Y/n] n
  [10/10] superpowers ...... plugin (manual: claude plugin install superpowers)

Step 4/5: Enabling cc-later modules...
  [x] later     — dispatch deferred tasks at window end
  [x] compact   — context recovery after compaction
  [x] resume    — auto-resume limit-hit tasks
  [x] budget    — global budget enforcement
  [x] window    — 5-hour window lifecycle
  [x] stats     — token analytics + cost tracking
  [x] nudge     — stale agent detection

Step 5/5: Writing configuration...
  ~/.cc-manager/cc-manager.toml       (created)
  ~/.cc-manager/dispatch.py           (created)
  ~/.claude/settings.json             (merged: 3 hook entries, 2 MCP servers)
  ~/.claude/cc-manager.md             (created)
  ~/.claude/CLAUDE.md                 (appended @cc-manager)

Done. Run `cc-manager status` to verify.
```

Flags:
- `--yes` — Non-interactive. Installs all recommended tools, enables all modules.
- `--minimal` — Enables cc-later modules only. No external tools.
- `--dry-run` — Print what would change without writing any files.

What `init` does NOT do:
- Delete any existing config (merge only)
- Install tools the user declines
- Modify project-level `.claude/` directories
- Create accounts or authenticate

---

### `cc-manager status`

Unified dashboard:

```
cc-manager v0.1.0

Modules (cc-later):
  later     ON   3 queued, 0 in-flight
  compact   ON   last triggered 2h ago
  resume    ON   0 pending resume
  budget    ON   4.2M / 10M tokens (42%)
  window    ON   187 min remaining
  stats     ON   tracking since 2026-03-15
  nudge     ON   0 stale agents

External tools:
  rtk             v0.25.0  (cargo)       60% avg savings
  ccusage         v0.8.1   (cargo)       standalone
  context7        latest   (mcp)         configured in settings.json
  playwright-mcp  latest   (mcp)         configured in settings.json
  agnix           v2.1.0   (npm)         standalone
  claude-squad    --       not installed

Config: ~/.cc-manager/cc-manager.toml
Hooks:  3 cc-manager entries (0 conflicts)
```

---

### `cc-manager module <name> <action>`

Actions: `enable`, `disable`, `status`.

```
$ cc-manager module later disable
Module 'later' disabled. Dispatcher will skip it.

$ cc-manager module later enable
Module 'later' enabled.

$ cc-manager module later status
later: enabled
  Queue: 3 tasks (1 priority, 2 normal)
  In-flight: 0 agents
  Last dispatch: 2026-04-06 10:00 UTC
  Config: max_entries_per_dispatch=3, model=sonnet
```

Module enable/disable does NOT edit settings.json. The dispatcher reads `cc-manager.toml` at runtime and skips disabled modules. This means toggling a module is a single TOML write.

---

### `cc-manager install <tool>`

Install an external tool from the registry.

```
$ cc-manager install ccusage
ccusage — Usage analytics CLI for Claude Code
Install method: cargo install ccusage
Proceed? [Y/n] y
Installing... done (v0.8.1).
Registered in ~/.cc-manager/registry/installed.json

$ cc-manager install context7
context7 — Version-specific library docs MCP server
This tool is an MCP server. Will add to ~/.claude/settings.json.
Proceed? [Y/n] y
Added MCP server 'context7' to settings.json.
Registered in ~/.cc-manager/registry/installed.json
```

If the tool has multiple install methods (e.g., cargo or npm), cc-manager picks the first one where the required package manager is available. If none are available, it prints an error with instructions.

Supports `--dry-run`.

---

### `cc-manager remove <tool>`

Remove an external tool. cc-manager cleans up its own registry and any settings.json entries it manages (MCP servers). It does NOT run the tool's uninstaller (too dangerous) -- it prints the uninstall command instead.

```
$ cc-manager remove ccusage
Removed ccusage from cc-manager registry.
To fully uninstall the binary: cargo uninstall ccusage

$ cc-manager remove context7
Removed context7 from cc-manager registry.
Removed MCP server 'context7' from settings.json.
```

---

### `cc-manager list [--available] [--installed] [--category=<cat>]`

List tools from the registry.

```
$ cc-manager list --installed
Installed tools (4):
  rtk             v0.25.0  recommended  Token-optimized CLI proxy
  ccusage         v0.8.1   recommended  Usage analytics CLI
  context7        latest   recommended  Version-specific docs MCP
  agnix           v2.1.0   recommended  Config linter (385 rules)

$ cc-manager list --available --category=memory
Available tools — memory:
  claude-mem          plugin    Persistent memory
  claude-supermemory  npm       Enhanced persistent memory (conflicts: claude-mem)
  mcp-memory-keeper   mcp       Long-term memory MCP server
  GoodMem             mcp       Memory management via MCP
```

---

### `cc-manager doctor`

Health check. Validates everything and reports issues.

```
$ cc-manager doctor

cc-manager doctor — system health check

Config:
  [OK]  cc-manager.toml is valid TOML
  [OK]  All config values within expected ranges

Modules:
  [OK]  later: enabled, handler.py exists, hook registered
  [OK]  compact: enabled, handler.py exists, hook registered
  [OK]  stats: enabled, collector.py exists, hook registered
  [OK]  nudge: enabled, handler.py exists, hook registered
  [WARN] resume: enabled but depends on later (OK — later is enabled)

Hooks:
  [OK]  3 cc-manager hook entries in settings.json
  [OK]  No hook conflicts detected
  [OK]  RTK PreToolUse hook present (not managed by cc-manager)

External tools:
  [OK]  rtk v0.25.0 (rtk --version)
  [OK]  ccusage v0.8.1 (ccusage --version)
  [OK]  context7 MCP server configured
  [FAIL] claude-squad: registered but binary not found in PATH
  [OK]  agnix v2.1.0 (agnix --version)

State:
  [OK]  state.json: valid, schema_version=1
  [OK]  JSONL files readable for window/budget

5 checks passed, 1 warning, 1 failure.
```

If `agnix` is installed, doctor also runs it against the config.

---

### `cc-manager backup [create|list|restore <timestamp>]`

Manual backup/restore of Claude Code configuration.

```
$ cc-manager backup create
Backed up:
  settings.json -> ~/.cc-manager/backups/settings.json.20260406-143000

$ cc-manager backup list
Available backups:
  20260406-143000  settings.json (4.2 KB)
  20260406-120000  settings.json (3.8 KB)

$ cc-manager backup restore 20260406-120000
Restoring settings.json from backup 20260406-120000...
Current settings.json backed up first as 20260406-143100.
Restored.
```

Backups are automatically created before any `init`, `install`, `remove`, or `module` operation that touches settings.json.

---

### `cc-manager uninstall [--keep-config]`

Complete removal:

1. Remove cc-manager's hook entries from settings.json
2. Remove MCP server entries cc-manager added to settings.json
3. Remove `~/.claude/cc-manager.md` and the `@cc-manager` line from CLAUDE.md
4. Remove `~/.claude/skills/cc-manager/`
5. Print list of external tools that were installed (user removes manually)
6. Unless `--keep-config`: remove `~/.cc-manager/`

---

### `cc-manager stats [--period=7d] [--format=table|json]`

Delegates to cc-later's stats module. Reads JSONL files directly.

```
$ cc-manager stats --period=7d

Token usage (last 7 days):
  Day         Input       Output      Cache       Est. Cost
  2026-03-31  1,200,000   320,000     890,000     $0.84
  2026-04-01  2,100,000   580,000     1,500,000   $1.52
  ...
  Total       9,800,000   2,400,000   7,200,000   $8.12

Model breakdown:
  Sonnet: 85% of tokens ($4.90)
  Opus:   15% of tokens ($3.22)

Window utilization: 72% (avg)
RTK savings: 64% (if rtk installed)
```

Pricing is configurable via `[stats.pricing]` in cc-manager.toml. Users can override default model prices when Anthropic changes pricing.

---

### `cc-manager config [get <key>|set <key> <value>|edit|reset]`

```
$ cc-manager config get stats.pricing.sonnet_input
3.00

$ cc-manager config set stats.pricing.sonnet_input 2.50
Updated stats.pricing.sonnet_input: 3.00 -> 2.50

$ cc-manager config edit
# Opens cc-manager.toml in $EDITOR

$ cc-manager config reset --confirm
Reset cc-manager.toml to defaults (backup created).
```

---

## 6. Config Format

Single file: `~/.cc-manager/cc-manager.toml`

TOML over .env because cc-manager has nested config (modules, tools, pricing tables). Comments are first-class. cc-later used .env for simplicity; cc-manager needs sections.

```toml
# cc-manager configuration
# Edit with: cc-manager config edit

[manager]
version = "0.1.0"
backup_on_change = true         # Auto-backup before any settings.json modification
log_level = "info"              # debug | info | warn | error

# ──────────────────────────────────────────
# Module: later
# ──────────────────────────────────────────
[later]
enabled = true
queue_path = ".claude/LATER.md"
max_entries_per_dispatch = 3
auto_gitignore = true

[later.dispatch]
enabled = true
model = "sonnet"
allow_file_writes = false
output_path = "~/.cc-manager/results/{repo}-{date}.json"

[later.window]
dispatch_mode = "window_aware"            # window_aware | time_based | always
trigger_at_minutes_remaining = 30
idle_grace_period_minutes = 10
fallback_dispatch_hours = []
jsonl_paths = []                          # Auto-detect if empty

# ──────────────────────────────────────────
# Module: compact
# ──────────────────────────────────────────
[compact]
enabled = true

# ──────────────────────────────────────────
# Module: resume
# ──────────────────────────────────────────
[resume]
enabled = true
min_remaining_minutes = 240

# ──────────────────────────────────────────
# Module: budget
# ──────────────────────────────────────────
[budget]
enabled = true
weekly_budget_tokens = 10_000_000
backoff_at_pct = 80

# ──────────────────────────────────────────
# Module: window
# ──────────────────────────────────────────
[window]
enabled = true
duration_minutes = 300

# ──────────────────────────────────────────
# Module: stats
# ──────────────────────────────────────────
[stats]
enabled = true
cost_tracking = true

# Configurable pricing (per 1M tokens, USD)
# Override when Anthropic changes pricing
[stats.pricing]
sonnet_input = 3.00
sonnet_output = 15.00
opus_input = 15.00
opus_output = 75.00
haiku_input = 0.25
haiku_output = 1.25
sonnet_cache_write = 3.75
sonnet_cache_read = 0.30
opus_cache_write = 18.75
opus_cache_read = 1.50
haiku_cache_write = 0.30
haiku_cache_read = 0.03

# ──────────────────────────────────────────
# Module: nudge
# ──────────────────────────────────────────
[nudge]
enabled = true
stale_minutes = 10
max_retries = 2

# ──────────────────────────────────────────
# External tools (installed state)
# ──────────────────────────────────────────
[tools.rtk]
enabled = true

[tools.ccusage]
enabled = true

[tools.context7]
enabled = true

[tools.claude-squad]
enabled = false                           # User declined during init
```

### Config resolution order

1. Environment variables: `CC_MANAGER_<SECTION>_<KEY>` (uppercased, dots become `_`)
2. `~/.cc-manager/cc-manager.toml`
3. Built-in defaults (hardcoded)

Environment overrides any TOML value. Example: `CC_MANAGER_LATER_ENABLED=false` overrides `[later] enabled = true`.

---

## 7. Module System

### Module contract

Every cc-later module is a Python package under `~/.cc-manager/modules/<name>/`. Each module declares:

```python
# modules/<name>/__init__.py

MODULE_NAME = "later"
MODULE_VERSION = "4.0.0"

# Hook events this module handles
HOOK_EVENTS = {
    "Stop": {
        "entry": "handler.py",
        "timeout_ms": 10000,
        "matcher": None,              # None = match all
    },
    "UserPromptSubmit": {
        "entry": "capture.py",
        "timeout_ms": 4000,
        "matcher": r"(?i)(later\s*(\[!\])?\s*:|add\s+(?:this\s+)?to\s+later\s*:)",
    },
}

# Optional
SKILLS = ["SKILL.md"]
CLAUDE_MD_DIRECTIVES = []
```

### Module lifecycle

When enabled:
1. Dispatcher includes the module when its hook events fire
2. Skills symlinked to `~/.claude/skills/cc-manager/<name>/`
3. CLAUDE.md directives appended to `~/.claude/cc-manager.md`
4. State section initialized in state.json

When disabled:
1. Dispatcher skips the module (no settings.json edit needed)
2. Skill symlinks removed
3. Directives removed from cc-manager.md
4. State preserved for re-enable

### Module failure isolation

The dispatcher wraps each module invocation in a try/except with a per-module timeout:

```
dispatch.py receives Stop event
  ├── later/handler.py    -> runs (10s timeout), succeeds
  ├── stats/collector.py  -> runs (5s timeout), CRASHES
  │   └── exception logged to run_log.jsonl, continues
  └── nudge/handler.py    -> runs (5s timeout), succeeds
```

If a module exceeds its timeout, the dispatcher kills it and moves on. The overall hook timeout in settings.json must be >= max(sum of per-module timeouts) but the dispatcher manages this internally by running modules that don't depend on each other concurrently where possible.

Doctor reports modules that have crashed in the last N runs.

### Built-in modules

| Module | Hook Events | Purpose |
|---|---|---|
| later | Stop, UserPromptSubmit | Queue parsing, task dispatch, result reconciliation |
| compact | SessionStart (matcher: "compact") | Re-inject LATER.md context after compaction |
| resume | (none -- logic in later) | Auto-resume failed tasks in fresh windows |
| budget | (none -- gate in later) | Weekly token budget enforcement |
| window | (none -- utility) | JSONL-based window state computation |
| stats | Stop | Token counting, cost estimation, session tracking |
| nudge | Stop | Detect stale agents, restart or kill |

### Shared state

Modules communicate via `~/.cc-manager/state/state.json`:

```json
{
  "schema_version": 1,
  "last_hook_ts": "2026-04-06T10:00:00+00:00",
  "window": {
    "elapsed_minutes": 113,
    "remaining_minutes": 187,
    "total_input_tokens": 450000,
    "total_output_tokens": 120000
  },
  "budget": {
    "used_tokens": 4200000,
    "pct_used": 0.42
  },
  "repos": {
    "/Users/user/Projects/myapp": {
      "in_flight": false,
      "agents": [],
      "resume_entries": [],
      "dispatch_ts": null
    }
  },
  "stats": {
    "sessions_tracked": 142,
    "total_input_tokens": 89000000,
    "total_output_tokens": 23000000,
    "estimated_cost_usd": 12.45,
    "tracking_since": "2026-03-15T00:00:00+00:00"
  },
  "module_health": {
    "later": {"last_success": "2026-04-06T10:00:00Z", "last_failure": null, "consecutive_failures": 0},
    "stats": {"last_success": "2026-04-06T09:55:00Z", "last_failure": "2026-04-06T10:00:00Z", "consecutive_failures": 1}
  }
}
```

Modules import shared logic from core:

```python
from cc_manager.core import (
    load_config,
    load_state,
    save_state,
    log_event,
    compute_window_state,
    compute_budget_state,
    app_dir,
)
```

---

## 8. Tool Registry (tools.json)

### Overview

The registry is a JSON file that ships with cc-manager. It is NOT a web service. It lives at `~/.cc-manager/registry/tools.json` and is replaced when cc-manager is upgraded.

User preferences (which tools are enabled/disabled) live in `cc-manager.toml`, not in tools.json. This means registry updates never overwrite user choices.

### Schema

```json
{
  "schema_version": 1,
  "last_updated": "2026-04-06",
  "tools": [
    {
      "name": "string (unique identifier, kebab-case)",
      "display_name": "string (human-readable)",
      "description": "string (one-line)",
      "tier": "recommended | popular | community",
      "category": "string (e.g., analytics, orchestration, memory)",
      "repo": "string (GitHub owner/repo)",
      "url": "string (optional, homepage URL)",
      "install_methods": [
        {
          "type": "cargo | npm | pip | go | brew | mcp | plugin | github_action | manual",
          "command": "string (shell command to run)",
          "requires": "string (optional, prerequisite binary)"
        }
      ],
      "remove_hint": "string (command to uninstall, printed but not executed)",
      "detect": {
        "command": "string (shell command, e.g., 'rtk --version')",
        "pattern": "string (regex to extract version from output)",
        "settings_json_key": "string (optional, for MCP/plugin detection)"
      },
      "integration": {
        "type": "standalone | hook | mcp_server | plugin | github_action | shell_plugin",
        "mcp_config": {
          "type": "stdio",
          "command": "string",
          "args": ["string"]
        },
        "hook_event": "string (optional, e.g., PreToolUse)",
        "managed_by": "string (optional, who owns the hook: 'self' or 'cc-manager')"
      },
      "conflicts_with": ["string (other tool names)"],
      "min_version": "string (optional, semver)"
    }
  ]
}
```

### Tiers

| Tier | Count | Behavior during `init` |
|---|---|---|
| recommended | 10 | Prompted individually, default Yes |
| popular | ~30 | Shown as grouped list, user picks |
| community | 160+ | Not shown during init; available via `cc-manager list --available` |

### Top 10 Recommended Tools (Data-Driven)

Ranked by cross-referencing GitHub stars, MCP install counts, awesome-list appearances (7 lists), and real user setup posts. These are tier "recommended" and offered during `cc-manager init`:

| # | Tool | Stars | Signal | Why |
|---|---|---|---|---|
| 1 | **Context7** | 51.8K | #1 MCP (690 installs) | Live version-specific docs. Universally recommended. |
| 2 | **GitHub MCP** | 28K | 204 installs | 51 tools for PRs, issues, CI. Essential for GitHub users. |
| 3 | **Playwright MCP** | 30K | #2 MCP (414 installs) | Official Microsoft. Browser automation standard. |
| 4 | **RTK** | 18.9K | 1K forks | 60-90% token savings via hook-based CLI filtering. |
| 5 | **feature-dev** | — | 89K installs | Most installed plugin. 7-phase workflow, 3 sub-agents. |
| 6 | **Superpowers** | 99K | 5/7 lists | Top skills framework. Official marketplace plugin. |
| 7 | **ccusage** | 12.4K | 4/7 lists | THE cost tracking tool for Claude Code. |
| 8 | **Claude Squad** | 6.9K | 6/7 lists | Most cross-listed. Parallel agent orchestration. |
| 9 | **repomix** | 23K | 4/7 lists | Packs entire repo for LLM context. MCP available. |
| 10 | **Trail of Bits** | 4.3K | 5/7 lists | Professional security auditing. Low stars, high signal. |

Detailed JSON registry entries for each:

#### 1. RTK (rtk-ai/rtk)
Token-optimized CLI proxy. 60-90% savings on dev operations.

```json
{
  "name": "rtk",
  "display_name": "RTK (Rust Token Killer)",
  "description": "Token-optimized CLI proxy, 60-90% savings on dev operations",
  "tier": "recommended",
  "category": "analytics",
  "repo": "rtk-ai/rtk",
  "install_methods": [
    {"type": "cargo", "command": "cargo install rtk"},
    {"type": "brew", "command": "brew install rtk-ai/tap/rtk"}
  ],
  "remove_hint": "cargo uninstall rtk",
  "detect": {
    "command": "rtk --version",
    "pattern": "rtk\\s+(\\d+\\.\\d+\\.\\d+)"
  },
  "integration": {
    "type": "hook",
    "hook_event": "PreToolUse",
    "managed_by": "rtk"
  },
  "min_version": "0.23.0"
}
```

Note: RTK manages its own hook. cc-manager detects it but does not register or modify it.

#### 2. ccusage (ryoppippi/ccusage)
Usage analytics CLI.

```json
{
  "name": "ccusage",
  "display_name": "ccusage",
  "description": "Usage analytics CLI for Claude Code",
  "tier": "recommended",
  "category": "analytics",
  "repo": "ryoppippi/ccusage",
  "install_methods": [
    {"type": "cargo", "command": "cargo install ccusage"},
    {"type": "npm", "command": "npm install -g ccusage"}
  ],
  "remove_hint": "cargo uninstall ccusage",
  "detect": {
    "command": "ccusage --version",
    "pattern": "(\\d+\\.\\d+\\.\\d+)"
  },
  "integration": {"type": "standalone"}
}
```

#### 3. Context7 (upstash/context7)
Version-specific library documentation MCP server.

```json
{
  "name": "context7",
  "display_name": "Context7",
  "description": "Version-specific library docs MCP server",
  "tier": "recommended",
  "category": "mcp-server",
  "repo": "upstash/context7",
  "install_methods": [
    {"type": "mcp"}
  ],
  "remove_hint": "Remove 'context7' from mcpServers in settings.json",
  "detect": {
    "settings_json_key": "mcpServers.context7"
  },
  "integration": {
    "type": "mcp_server",
    "mcp_config": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@context7/mcp"]
    }
  }
}
```

#### 4. Playwright MCP (microsoft/playwright)
Browser automation via MCP.

```json
{
  "name": "playwright-mcp",
  "display_name": "Playwright MCP",
  "description": "Browser automation via MCP",
  "tier": "recommended",
  "category": "mcp-server",
  "repo": "microsoft/playwright-mcp",
  "install_methods": [
    {"type": "mcp"}
  ],
  "remove_hint": "Remove 'playwright' from mcpServers in settings.json",
  "detect": {
    "settings_json_key": "mcpServers.playwright"
  },
  "integration": {
    "type": "mcp_server",
    "mcp_config": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@anthropic/playwright-mcp"]
    }
  }
}
```

#### 5. Claude Squad (smtg-ai/claude-squad)
Multi-agent tmux orchestration TUI.

```json
{
  "name": "claude-squad",
  "display_name": "Claude Squad",
  "description": "Multi-agent tmux orchestration TUI",
  "tier": "recommended",
  "category": "orchestration",
  "repo": "smtg-ai/claude-squad",
  "install_methods": [
    {"type": "go", "command": "go install github.com/smtg-ai/claude-squad@latest"},
    {"type": "brew", "command": "brew install smtg-ai/tap/claude-squad"}
  ],
  "remove_hint": "rm $(which cs)",
  "detect": {
    "command": "cs --version",
    "pattern": "(\\d+\\.\\d+\\.\\d+)"
  },
  "integration": {"type": "standalone"}
}
```

#### 6. agnix (agent-sh/agnix)
Config linter with 385 rules. Used by `doctor`.

```json
{
  "name": "agnix",
  "display_name": "agnix",
  "description": "Config linter for Claude Code (385 rules)",
  "tier": "recommended",
  "category": "config",
  "repo": "agent-sh/agnix",
  "install_methods": [
    {"type": "npm", "command": "npm i -g @agent-sh/agnix"}
  ],
  "remove_hint": "npm uninstall -g @agent-sh/agnix",
  "detect": {
    "command": "agnix --version",
    "pattern": "(\\d+\\.\\d+\\.\\d+)"
  },
  "integration": {"type": "standalone"}
}
```

#### 7. Trail of Bits Security Skills (trailofbits/skills)
Security auditing skills for Claude Code.

```json
{
  "name": "trail-of-bits",
  "display_name": "Trail of Bits Security Skills",
  "description": "Security-focused auditing skills",
  "tier": "recommended",
  "category": "security",
  "repo": "trailofbits/claude-code-security",
  "install_methods": [
    {"type": "plugin", "command": "claude plugin install trailofbits-skills"}
  ],
  "remove_hint": "claude plugin uninstall trailofbits-skills",
  "detect": {
    "settings_json_key": "enabledPlugins",
    "pattern": "trailofbits"
  },
  "integration": {"type": "plugin"}
}
```

#### 8. claude-code-action (anthropics/claude-code-action)
GitHub Actions CI/CD integration.

```json
{
  "name": "claude-code-action",
  "display_name": "Claude Code Action",
  "description": "GitHub Actions CI/CD for Claude Code",
  "tier": "recommended",
  "category": "ci-cd",
  "repo": "anthropics/claude-code-action",
  "install_methods": [
    {"type": "github_action"}
  ],
  "remove_hint": "Remove claude.yml from .github/workflows/",
  "detect": {
    "command": "test -f .github/workflows/claude.yml && echo found",
    "pattern": "found"
  },
  "integration": {
    "type": "github_action",
    "setup_instructions": "Copy workflow template to .github/workflows/claude.yml"
  }
}
```

#### 9. code-review-graph (tirth8205/code-review-graph)
Knowledge graph for code review.

```json
{
  "name": "code-review-graph",
  "display_name": "Code Review Graph",
  "description": "Knowledge graph for code review context",
  "tier": "recommended",
  "category": "code-review",
  "repo": "tirth8205/code-review-graph",
  "install_methods": [
    {"type": "pip", "command": "pip install code-review-graph"}
  ],
  "remove_hint": "pip uninstall code-review-graph",
  "detect": {
    "command": "code-review-graph --version",
    "pattern": "(\\d+\\.\\d+\\.\\d+)"
  },
  "integration": {"type": "mcp_server"}
}
```

#### 10. Superpowers (obra/superpowers)
Structured dev lifecycle skills.

```json
{
  "name": "superpowers",
  "display_name": "Superpowers",
  "description": "Structured dev lifecycle skills",
  "tier": "recommended",
  "category": "skills",
  "repo": "obra/superpowers",
  "install_methods": [
    {"type": "plugin", "command": "claude plugin install superpowers"}
  ],
  "remove_hint": "claude plugin uninstall superpowers",
  "detect": {
    "settings_json_key": "enabledPlugins",
    "pattern": "superpowers"
  },
  "integration": {"type": "plugin"},
  "conflicts_with": ["simone"]
}
```

### Full Registry by Category (200+ verified tools)

Below is the complete catalog organized by category. Data sourced from 7 awesome lists, GitHub stars, MCP install metrics, Reddit user recommendations, and Anthropic marketplace data. Each entry in the actual tools.json follows the schema above.

**Adoption signals legend:**
- Stars: GitHub star count (verified April 2026)
- Lists: appearances across 7 major awesome-claude-code lists
- Installs: MCP directory or marketplace install count

#### Multi-Agent Orchestration
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| claude-squad | recommended | 6.9K | 6/7 | smtg-ai/claude-squad | go/brew |
| claude-swarm | popular | — | 5/7 | parruda/claude-swarm | npm |
| ruflo | popular | 30K | 3/7 | ruvnet/ruflo | npm |
| oh-my-claudecode | popular | 25K | 2/7 | Yeachan-Heo/oh-my-claudecode | npm |
| auto-claude | community | — | 4/7 | AndyMik90/Auto-Claude | pip |
| happy-coder | community | — | — | slopus/happy | npm |
| tsk | community | — | — | dtormoen/tsk | cargo |
| sudocode | community | — | 3/7 | sudocode-ai/sudocode | npm |
| parallel-code | community | — | — | johannesjo/parallel-code | npm |
| parallel-worktrees | community | — | — | SpillwaveSolutions/parallel-worktrees | pip |
| claude-code-by-agents | community | — | — | baryhuang/claude-code-by-agents | npm |
| agent-flow | community | — | — | patoles/agent-flow | npm |

#### Task Management
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| claude-task-master | popular | 26.4K | 5/7 | eyaltoledano/claude-task-master | npm/mcp |
| claude-code-pm | popular | — | — | automazeio/ccpm | plugin |
| simone | popular | — | 4/7 | Helmi/claude-simone | plugin |
| claude-task-runner | community | — | — | grahama1970/claude-task-runner | npm |
| shrimp-task-manager | community | — | — | cjo4m06/mcp-shrimp-task-manager | mcp |
| scopecraft-command | community | — | — | scopecraft/command | npm |
| steadystart | community | — | — | steadycursor/steadystart | plugin |

#### Memory and Context
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| claude-mem | popular | 46K | 3/7 | thedotmack/claude-mem | plugin |
| claude-supermemory | popular | — | — | supermemoryai/claude-supermemory | npm |
| claude_memory | community | — | — | codenamev/claude_memory | pip |
| mcp-memory-keeper | community | — | — | mkreyman/mcp-memory-keeper | mcp |
| GoodMem | community | — | — | (official plugin) | plugin |
| remember | community | — | — | (official plugin) | plugin |
| claude-session-restore | community | — | — | ZENG3LD/claude-session-restore | npm |
| recall | popular | — | 5/7 | zippoxer/recall | mcp |
| context-engineering-kit | community | — | — | NeoLabHQ/context-engineering-kit | pip |
| contextkit | community | — | 3/7 | FlineDev/ContextKit | npm |
| context-mode | community | — | — | mksglu/claude-context-mode | plugin |

#### Usage Analytics
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| rtk | recommended | 18.9K | 3+ | rtk-ai/rtk | cargo/brew |
| ccusage | recommended | 12.4K | 4/7 | ryoppippi/ccusage | cargo/npm |
| ccflare | popular | — | 4/7 | snipeship/ccflare | npm |
| better-ccflare | community | — | — | tombii/better-ccflare | npm |
| claude-code-usage-monitor | community | — | — | Maciek-roboblog/Claude-Code-Usage-Monitor | npm |
| myccusage | community | — | — | i-richardwang/MyCCusage | npm |
| claude-code-usage-analyzer | community | — | — | aarora79/claude-code-usage-analyzer | pip |
| tokscale | community | — | — | junhoyeo/tokscale | cargo |
| viberank | community | — | — | sculptdotfun/viberank | npm |
| vibe-log | community | — | — | vibe-log/vibe-log-cli | npm |
| manifest | community | — | — | mnfst/manifest | npm |
| ccrank | community | — | — | ccranking.github.io | npm |

#### Terminal UI and Statuslines
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| ccstatusline | popular | — | 3/7 | sirmalloc/ccstatusline | npm |
| claude-powerline | popular | — | 4/7 | Owloops/claude-powerline | npm |
| claudia-statusline | community | — | — | hagan/claudia-statusline | cargo |
| ccometixline | community | — | — | Haleclipse/CCometixLine | cargo |
| tweakcc | community | — | 4/7 | Piebald-AI/tweakcc | npm |
| claude-tmux | community | — | — | nielsgroen/claude-tmux | pip |
| codeman | community | — | — | Ark0N/Codeman | npm |

#### IDE Integrations
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| claude-code.nvim | popular | — | 5/7 | greggh/claude-code.nvim | manual |
| claude-code.el | community | — | 3/7 | stevemolitor/claude-code.el | manual |
| claude-code-ide.el | community | — | — | manzaltu/claude-code-ide.el | manual |
| claude-code-chat-vscode | community | — | — | (VS Code Marketplace) | manual |
| claudix | community | — | 4/7 | Haleclipse/Claudix | npm |

#### Docker and Sandboxing
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| container-use | popular | — | 4/7 | dagger/container-use | mcp |
| claude-sandbox | community | — | — | nkrefman/claude-sandbox | pip |
| claude-code-sandbox | community | — | — | textcortex/claude-code-sandbox | npm |
| claude-code-devcontainer | community | — | — | trailofbits/claude-code-devcontainer | manual |
| sbox | community | — | — | streamingfast/sbox | cargo |
| run-claude-docker | community | — | 4/7 | icanhasjonas/run-claude-docker | pip |
| viwo-cli | community | — | — | OverseedAI/viwo | npm |

#### Hooks and Automation
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| claude-code-hooks-mastery | popular | — | — | disler/claude-code-hooks-mastery | manual |
| claude-code-hooks-observability | community | — | — | disler/claude-code-hooks-multi-agent-observability | manual |
| claude-hooks | community | — | — | johnlindquist/claude-hooks | npm |
| cc-tools | community | — | — | Veraticus/cc-tools | go |
| hookify | community | — | — | (official plugin) | plugin |

#### CI/CD
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| claude-code-action | recommended | — | 4/7 | anthropics/claude-code-action | github_action |
| claude-hub | community | — | 3/7 | claude-did-this/claude-hub | github_action |

#### Config and Linting
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| agnix | popular | — | — | agent-sh/agnix | npm |
| cclint | community | — | — | carlrannaberg/cclint | npm |
| claude-rules-doctor | community | — | — | nulone/claude-rules-doctor | pip |
| claudectx | community | — | 3/7 | foxj77/claudectx | npm |
| rulesync | community | — | 3/7 | dyoshikawa/rulesync | npm |
| claude-rules | community | — | — | lifedever/claude-rules | plugin |

#### Session and History
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| cchistory | popular | — | — | eckardt/cchistory | npm |
| cclogviewer | community | — | — | Brads3290/cclogviewer | npm |
| claudex | community | — | 3/7 | kunwar-shah/claudex | pip |
| claude-devtools | community | — | 3/7 | matt1398/claude-devtools | npm |
| claude-code-tools | community | — | — | pchalasani/claude-code-tools | pip |
| ccexp | community | — | — | nyatinte/ccexp | npm |

#### MCP Servers
| Tool | Tier | Stars | Installs | Repo | Install Type |
|---|---|---|---|---|---|
| context7 | recommended | 51.8K | 690 | upstash/context7 | mcp |
| playwright-mcp | recommended | 30K | 414 | microsoft/playwright-mcp | mcp |
| github-mcp | recommended | 28K | 204 | github/github-mcp-server | mcp |
| sequential-thinking | popular | — | 569 | modelcontextprotocol/servers | mcp |
| desktop-commander | popular | 5.5K | — | wonderwhy-er/DesktopCommanderMCP | mcp |
| claude-code-mcp | community | — | — | steipete/claude-code-mcp | mcp |
| claude-context | community | — | — | zilliztech/claude-context | mcp |
| perplexity-mcp | community | — | — | perplexityai/modelcontextprotocol | mcp |
| firecrawl-mcp | community | — | — | (official plugin) | mcp |

#### Voice
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| voice-to-claude | community | — | — | enesbasbug/voice-to-claude | npm |
| claude-stt | community | — | — | jarrodwatts/claude-stt | pip |
| claude-code-voice | community | — | — | jdpsc/claude-code-voice | npm |
| listen-claude-code | community | — | — | gmoqa/listen-claude-code | npm |
| voicemode-mcp | community | — | 3/7 | mbailey/voicemode | mcp |

#### Code Review
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| code-review-graph | popular | — | — | tirth8205/code-review-graph | pip/mcp |
| local-review | popular | — | — | (official plugin) | plugin |
| diffity | community | — | — | kamranahmedse/diffity | npm |
| claude-review-loop | community | — | — | hamelsmu/claude-review-loop | plugin |
| agent-peer-review | community | — | — | jcputney/agent-peer-review | pip |
| claude-code-quality-hook | community | — | — | dhofheinz/claude-code-quality-hook | npm |

#### Security
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| trail-of-bits-skills | recommended | 4.3K | 5/7 | trailofbits/skills | plugin |
| semgrep | popular | — | — | (official plugin) | plugin |
| aikido | community | — | — | (official plugin) | plugin |
| coderabbit | community | — | — | (official plugin) | plugin |
| sonarqube | community | — | — | (official plugin) | plugin |
| sentry | community | — | — | (official plugin) | plugin |
| endor-labs | community | — | — | (official plugin) | plugin |

#### Skills and Frameworks
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| superpowers | recommended | 99K | 5/7 | obra/superpowers | plugin |
| everything-claude-code | popular | 142K | 5/7 | affaan-m/everything-claude-code | plugin |
| superclaude | popular | — | 6/7 | SuperClaude-Org/SuperClaude_Framework | plugin |
| feature-dev | popular | — | — | (official plugin, 89K installs) | plugin |
| compound-engineering | popular | 13K | 3/7 | EveryInc/compound-engineering-plugin | plugin |
| claude-codepro | community | — | — | maxritter/claude-codepro | plugin |
| claudekit | community | — | 3/7 | carlrannaberg/claudekit | npm |
| cc-devops-skills | community | — | — | akin-ozer/cc-devops-skills | plugin |
| voltagent-subagents | community | 16K | — | VoltAgent/awesome-claude-code-subagents | npm |
| antigravity-skills | community | 31K | 3/7 | sickn33/antigravity-awesome-skills | plugin |
| anthropics-skills | popular | 111K | — | anthropics/skills | plugin |

#### Workflow and Methodology
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| bmad-method | popular | 44K | 4/7 | bmad-code-org/BMAD-METHOD | plugin |
| get-shit-done | popular | 48K | 3/7 | gsd-build/get-shit-done | plugin |
| riper-workflow | popular | — | — | tony/claude-code-riper-5 | plugin |
| ab-method | community | — | — | ayoubben18/ab-method | plugin |
| ralph-loop | community | — | 4/7 | (official plugin) | plugin |
| ralph-orchestrator | community | — | — | mikeyobrien/ralph-orchestrator | npm |
| simone | popular | — | 4/7 | Helmi/claude-simone | plugin |
| planning-with-files | popular | — | 4/7 | — | skill |

#### Observability
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| signoz-dashboard | community | — | — | (SigNoz template) | manual |
| grafana-plugin | community | — | — | (Grafana marketplace) | manual |
| claude-code-otel | community | — | — | ColeMurray/claude-code-otel | npm |
| claude-devtools | community | — | 3/7 | matt1398/claude-devtools | npm |
| vibe-log | community | — | — | vibe-log/vibe-log-cli | npm |

#### Context and Repo Packaging
| Tool | Tier | Stars | Lists | Repo | Install Type |
|---|---|---|---|---|---|
| repomix | popular | 23K | 4/7 | yamadashy/repomix | npm/mcp |
| cc-switch | popular | 40K | 2/7 | farion1231/cc-switch | npm |

#### Official Partner Integrations (MCP)
| Tool | Tier | Repo | Install Type |
|---|---|---|---|
| github-mcp | popular | github/github-mcp-server | mcp |
| figma-mcp | popular | figma/mcp-server-guide | mcp |
| linear-mcp | popular | (official plugin) | mcp |
| atlassian-mcp | popular | (official plugin) | mcp |
| slack-mcp | popular | (official plugin) | mcp |
| notion-mcp | popular | (official plugin) | mcp |
| supabase-mcp | popular | supabase (official docs) | mcp |
| firebase-mcp | popular | (official plugin) | mcp |
| vercel-mcp | popular | vercel/vercel-deploy-claude-code-plugin | mcp |
| stripe-mcp | popular | (official plugin) | mcp |
| posthog-mcp | popular | (official plugin) | mcp |
| firecrawl-mcp | popular | (official plugin) | mcp |
| neon-mcp | community | (official plugin) | mcp |
| railway-mcp | community | (official plugin) | mcp |
| terraform-mcp | community | (official plugin) | mcp |
| zapier-mcp | community | (official plugin) | mcp |
| brightdata-mcp | community | (official plugin) | mcp |

#### Curated Lists and Directories
| Resource | Stars | URL |
|---|---|---|
| awesome-claude-code | 36.9K | hesreallyhim/awesome-claude-code |
| awesome-claude-plugins (quemsah) | — | quemsah/awesome-claude-plugins (10.9K repos indexed) |
| awesome-claude-code-plugins | — | ccplugins/awesome-claude-code-plugins |
| awesome-claude-code-toolkit | — | rohitg00/awesome-claude-code-toolkit |
| awesome-claude-plugins (Composio) | — | ComposioHQ/awesome-claude-plugins |
| buildwithclaude | — | davepoon/buildwithclaude |
| claude-plugins-official | 16K | anthropics/claude-plugins-official (123 plugins) |
| claude-code-tips | 3.1K | ykdojo/claude-code-tips |
| Claude Marketplaces | — | claudemarketplaces.com (2,500+ skills) |

### installed.json

Tracks what cc-manager has installed:

```json
{
  "schema_version": 1,
  "tools": {
    "rtk": {
      "version": "0.25.0",
      "installed_at": "2026-04-06T12:00:00Z",
      "install_method": "cargo",
      "managed_mcp": null
    },
    "context7": {
      "version": "latest",
      "installed_at": "2026-04-06T12:00:00Z",
      "install_method": "mcp",
      "managed_mcp": "context7"
    }
  }
}
```

### Conflict detection

Some tools conflict (e.g., claude-mem vs claude-supermemory). The `conflicts_with` field prevents installing both:

```
$ cc-manager install claude-supermemory
WARNING: claude-supermemory conflicts with claude-mem (already installed).
Both provide memory functionality.
Install anyway? [y/N]
```

---

## 9. Dispatcher Architecture

### The problem

Claude Code's settings.json has a single `hooks` object. Multiple tools register hooks on the same events. Manual management is error-prone (last-write-wins, silent conflicts).

### Solution: single dispatcher per event

cc-manager registers one hook entry per event in settings.json. The dispatcher reads cc-manager.toml at runtime to determine which modules are enabled, then calls each one.

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.cc-manager/dispatch.py Stop",
            "timeout": 15000
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "(?i)(later\\s*(\\[!\\])?\\s*:|add\\s+(?:this\\s+)?to\\s+later\\s*:)",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.cc-manager/dispatch.py UserPromptSubmit",
            "timeout": 5000
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "compact",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.cc-manager/dispatch.py SessionStart",
            "timeout": 5000
          }
        ]
      }
    ]
  }
}
```

This means:
- Adding/removing modules does NOT change settings.json (the dispatcher reads config)
- Module enable/disable is a TOML write, not a JSON merge
- cc-manager owns exactly 3 hook entries (Stop, UserPromptSubmit, SessionStart)
- Non-cc-manager hooks (RTK, plugins, user hooks) are untouched

### Dispatcher flow

```
stdin (hook payload JSON) -> dispatch.py <event_name>
  1. Parse event name from argv[1]
  2. Read hook payload from stdin
  3. Load cc-manager.toml (cached per invocation)
  4. For each enabled module that handles this event:
     a. Import module's entry point
     b. Call it with the payload, wrapped in try/except
     c. Enforce per-module timeout (signal.alarm or threading.Timer)
     d. Log result (success/failure/timeout) to run_log.jsonl
     e. Record health in state.json module_health
  5. If any module returns output, write it to stdout
  6. Exit 0 (even if individual modules failed -- isolation)
```

### Failure model

- **Module crashes:** Exception caught, logged, next module runs. Exit code still 0.
- **Module timeout:** Killed after its timeout_ms. Logged as timeout. Next module runs.
- **Config unreadable:** Dispatcher exits with error (no modules run). Doctor would catch this.
- **All modules disabled:** Dispatcher does nothing, exits 0.
- **Consecutive failures:** After 3 consecutive failures, doctor flags the module. The dispatcher still attempts it each time (no auto-disable).

---

## 10. settings.json Management

### Read-modify-write protocol

```
1. LOCK    — fcntl.flock on a lockfile (~/.cc-manager/.settings.lock)
2. READ    — json.load the current settings.json
3. BACKUP  — copy to ~/.cc-manager/backups/
4. MODIFY  — apply changes to the in-memory dict
5. WRITE   — json.dump with indent=2, trailing newline
6. UNLOCK  — release lock
```

### What cc-manager writes

| Section | What | When |
|---|---|---|
| `hooks` | cc-manager dispatcher entries (identified by command path) | init, uninstall |
| `mcpServers` | MCP server configs for tools with `integration.type == "mcp_server"` | install, remove |

cc-manager does NOT modify: `enabledPlugins`, `extraKnownMarketplaces`, `allowedTools`, `cleanupPeriodDays`, or any other field.

### Identification

cc-manager identifies its own hook entries by the command path containing `~/.cc-manager/dispatch.py`. This is the only criteria. On uninstall, it removes exactly those entries.

### MCP server management

For tools with MCP integration, `cc-manager install` adds the server config:

```json
{
  "mcpServers": {
    "context7": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@context7/mcp"]
    }
  }
}
```

`cc-manager remove context7` removes the key. If the user has manually modified the config (different args, added env vars), cc-manager warns before overwriting.

---

## 11. Migration from cc-later

When `cc-manager init` detects an existing cc-later installation (`~/.cc-later/` exists or cc-later plugin is enabled):

1. Read `~/.cc-later/config.env` (or `default_config.toml`) and convert to TOML sections
2. Copy `~/.cc-later/state.json` to `~/.cc-manager/state/state.json`
3. Copy `~/.cc-later/run_log.jsonl` to `~/.cc-manager/state/run_log.jsonl`
4. Copy result files and worktrees
5. Remove cc-later's plugin hook entries from settings.json
6. Print: "Migrated from cc-later. Old config preserved at ~/.cc-later/ (not deleted)."

cc-later's directory is NOT deleted. User removes it manually when satisfied.

If cc-later is not detected, init proceeds normally.

---

## 12. Implementation Plan

### Phase 1: Skeleton (week 1)

**Files to create:**

```
cc-manager/
├── pyproject.toml
├── cc_manager/
│   ├── __init__.py
│   ├── cli.py              # argparse entry point
│   ├── core.py             # Config loading, state, logging, shared utils
│   ├── _toml_compat.py     # Minimal TOML reader for Python 3.10
│   ├── settings.py         # settings.json read-modify-write with locking
│   └── registry.py         # tools.json loading, install/remove logic
├── registry/
│   └── tools.json          # Ships with package
└── tests/
    └── ...
```

Deliverables:
- `cc-manager --version` works
- `cc-manager config get/set/edit` works
- settings.json locking works
- TOML config loads with env var overrides

### Phase 2: Init and modules (week 2)

**Files to add:**

```
cc_manager/
├── init.py                 # Init flow (detect, backup, merge, configure)
├── modules.py              # Module enable/disable/status
├── backup.py               # Backup create/list/restore
├── dispatch.py             # The hook dispatcher (installed to ~/.cc-manager/)
└── modules/                # Vendored cc-later modules
    ├── later/
    ├── compact/
    ├── resume/
    ├── budget/
    ├── window/
    ├── stats/
    └── nudge/
```

Deliverables:
- `cc-manager init` runs end-to-end (detect env, create dirs, backup, enable modules, write hooks)
- `cc-manager init --dry-run` shows what would change
- `cc-manager module <name> enable/disable/status` works
- Dispatcher calls modules and handles failures
- `cc-manager backup create/list/restore` works

### Phase 3: Tool management (week 3)

**Files to add:**

```
cc_manager/
├── tools.py                # install/remove/list logic
└── doctor.py               # Health checks
```

Deliverables:
- `cc-manager install <tool>` works (cargo, npm, pip, go, mcp, plugin types)
- `cc-manager remove <tool>` works
- `cc-manager list --installed / --available / --category` works
- installed.json tracking
- Conflict detection
- `cc-manager doctor` runs all checks

### Phase 4: Status, stats, uninstall (week 4)

**Files to add/modify:**

```
cc_manager/
├── status.py               # Unified status dashboard
├── stats.py                # Delegates to cc-later stats module
└── uninstall.py            # Clean removal
```

Deliverables:
- `cc-manager status` shows full dashboard
- `cc-manager stats` shows token analytics with configurable pricing
- `cc-manager uninstall` cleanly removes everything
- Migration from cc-later works
- All commands support `--dry-run` where applicable

### Phase 5: Testing and polish (week 5)

- Unit tests for all commands
- Integration tests (mock settings.json, test merge/backup/restore)
- Test dispatcher failure isolation
- Test migration from cc-later
- Test conflict detection
- README and CHANGELOG

---

## Appendices

### Appendix A: File Ownership Map

| Path | Owner | cc-manager access |
|---|---|---|
| `~/.cc-manager/` | cc-manager | Full control |
| `~/.claude/settings.json` | Claude Code | Read-modify-write (hooks + mcpServers only) |
| `~/.claude/CLAUDE.md` | User | Append/remove one line |
| `~/.claude/cc-manager.md` | cc-manager | Create/delete |
| `~/.claude/skills/cc-manager/` | cc-manager | Create/delete |
| `~/.claude/plugins/` | Claude Code | Read only (detect installed plugins) |
| `~/.claude/projects/` | Claude Code | Read only (JSONL for window/budget) |
| `~/.claude/history.jsonl` | Claude Code | Never touch |
| `~/.claude/sessions/` | Claude Code | Never touch |

### Appendix B: Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `CC_MANAGER_DIR` | Override cc-manager home directory | `~/.cc-manager` |
| `CC_MANAGER_CONFIG` | Override config file path | `$CC_MANAGER_DIR/cc-manager.toml` |
| `CC_MANAGER_LOG_LEVEL` | Override log level | `info` |
| `CC_MANAGER_<SECTION>_<KEY>` | Override any config value | (from toml) |
| `CLAUDE_CONFIG_DIR` | Claude Code's config dir (respected) | `~/.claude` |

### Appendix C: Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | General error |
| 2 | Config error (invalid TOML, missing field) |
| 3 | Hook conflict detected |
| 4 | External tool not found |
| 5 | Migration failed |
| 10 | settings.json lock timeout |

### Appendix D: Architecture Decision Record

**Why cc-manager is separate from cc-later:**
cc-later is a focused plugin (idle capacity reclamation). cc-manager is an ecosystem tool (installs tools, manages config, runs diagnostics). Bundling cc-later into cc-manager keeps cc-later's codebase unchanged while adding value on top. Users who want just cc-later can keep using the plugin directly.

**Why TOML over .env:**
cc-later used .env for flat config. cc-manager needs nested sections (8 modules, pricing tables, per-tool config). TOML provides sections, lists, inline tables, and comments. Python 3.11+ has `tomllib` in stdlib. For 3.10, a ~100 line compat reader ships with cc-manager.

**Why single dispatcher over per-module hooks:**
- Fewer entries in settings.json (3 vs 10+)
- Module enable/disable does not require editing settings.json
- Guaranteed execution order
- Failure isolation within the dispatcher
- Single timeout per event, managed internally

**Why tools.json is a local file, not a web service:**
- Zero network dependency
- Works offline
- Ships with cc-manager, updated on upgrade
- No auth, no rate limits, no downtime
- Future: optional `cc-manager registry update` fetches latest from GitHub

**Why cc-manager does not run tool uninstallers:**
Running `cargo uninstall X` or `pip uninstall X` is destructive. cc-manager prints the command instead. The user decides when and how to remove the binary. cc-manager only cleans up its own registry and settings.json entries.

**Why per-module failure isolation:**
A bug in the stats collector should not prevent LATER.md dispatch. Each module runs in its own try/except. Timeouts are enforced. The dispatcher logs failures and continues. Doctor reports health. This is the key difference from cc-later's monolithic handler.py.

---

## Appendix B: Claude Code Ecosystem Tools Registry

A comprehensive catalog of 130+ tools in the Claude Code / AI coding agent ecosystem. This registry informs cc-manager's `tools.json` and helps identify integration opportunities.

> Last updated: 2026-04-06

---

### Category 1: CLI Output Compression & Filtering

Tools that reduce token usage by compressing/filtering shell output before it reaches the LLM.

| # | Name | Repo | Description |
|---|------|------|-------------|
| 1 | RTK | [rtk-ai/rtk](https://github.com/rtk-ai/rtk) | Rust binary CLI proxy, 60-90% token savings on 100+ dev commands, <10ms overhead |
| 2 | Tamp | [sliday/tamp](https://github.com/sliday/tamp) | Token compression proxy; minifies JSON, normalizes text/code, ~52% fewer tokens |
| 3 | Headroom | [chopratejas/headroom](https://github.com/chopratejas/headroom) | Auto-detects content type (JSON, code, logs), routes to best compressor, 70-90% savings |
| 4 | Headroom Desktop | [gglucass/headroom-desktop](https://github.com/gglucass/headroom-desktop) | macOS tray app chaining headroom + rtk with savings analytics |
| 5 | Context Mode | [mksglu/context-mode](https://github.com/mksglu/context-mode) | Sandboxes tool output in subprocesses, stores events in SQLite with FTS5/BM25, 98% reduction |
| 6 | Caveman | [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | Skill that cuts ~75% of tokens by forcing terse output while maintaining accuracy |
| 7 | Caveman Claude | [om-patel5/Caveman-Claude](https://github.com/om-patel5/Caveman-Claude) | Optimization layer to maximize context window utility and reduce inference costs |
| 8 | Claw Compactor | [open-compress/claw-compactor](https://github.com/open-compress/claw-compactor) | 6-layer deterministic context compression, up to 97% savings, no LLM required |

---

### Category 2: Token & Cost Monitoring

Tools that track, visualize, or alert on token usage and costs.

| # | Name | Repo | Description |
|---|------|------|-------------|
| 9 | ccusage | [ryoppippi/ccusage](https://github.com/ryoppippi/ccusage) | CLI analyzing local JSONL files; daily/monthly/session breakdowns, cache token support (~4.8k stars) |
| 10 | better-ccusage | [cobra91/better-ccusage](https://github.com/cobra91/better-ccusage) | Extended fork with multi-provider support (Anthropic, Zai, Dashscope) |
| 11 | Claude Code Usage Monitor | [Maciek-roboblog/Claude-Code-Usage-Monitor](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor) | Real-time terminal monitor with ML-based predictions and burn rate analysis |
| 12 | claude-code-usage-analyzer | [aarora79/claude-code-usage-analyzer](https://github.com/aarora79/claude-code-usage-analyzer) | Comprehensive cost analyzer with LiteLLM pricing data |
| 13 | Claude-Code-Usage-Tracker | [LyndonWangWork/Claude-Code-Usage-Tracker](https://github.com/LyndonWangWork/Claude-Code-Usage-Tracker) | Lightweight utility parsing activity logs for usage trends |
| 14 | TokenBar | [tokenbar.site](https://www.tokenbar.site/) | macOS menu bar app for real-time token usage across OpenAI, Claude, Gemini ($5) |
| 15 | CodexBar | [steipete/CodexBar](https://github.com/steipete/CodexBar) | macOS 14+ menu bar showing stats for Codex, Claude Code, Cursor, Gemini |
| 16 | ai-token-monitor | [soulduse/ai-token-monitor](https://github.com/soulduse/ai-token-monitor) | System tray app (macOS/Windows) tracking Claude Code and Codex costs |
| 17 | Claude-Usage-Tracker (macOS) | [hamed-elfayome/Claude-Usage-Tracker](https://github.com/hamed-elfayome/Claude-Usage-Tracker) | Native Swift/SwiftUI menu bar app for Claude usage limits |
| 18 | tokscale | [junhoyeo/tokscale](https://github.com/junhoyeo/tokscale) | CLI tracking tokens from Claude Code, Codex, Gemini, Cursor with global leaderboard |
| 19 | PreflightLLMCost | [aatakansalar/PreflightLLMCost](https://github.com/aatakansalar/PreflightLLMCost) | Preflight cost forecasting before API call execution |
| 20 | llm-prices | [simonw/llm-prices](https://github.com/simonw/llm-prices) | Maintained dataset of LLM pricing across providers (llm-prices.com) |
| 21 | cccost | [badlogic/cccost](https://github.com/badlogic/cccost) | Hooks NodeJS fetch() to intercept API requests and track actual cost in real-time |
| 22 | ccost | [toolsu/ccost](https://github.com/toolsu/ccost) | Rust CLI for analyzing token usage from local logs; powers CC Dashboard (Tauri app) |
| 23 | claude-code-usage | [evanlong-me/claude-code-usage](https://github.com/evanlong-me/claude-code-usage) | CLI to track Claude Code usage, costs, and token consumption locally |
| 24 | Claud-ometer | [deshraj/Claud-ometer](https://github.com/deshraj/Claud-ometer) | Local-first analytics dashboard for Claude Code, no cloud/telemetry |
| 25 | claude-code-dashboard | [Stargx/claude-code-dashboard](https://github.com/Stargx/claude-code-dashboard) | Localhost dashboard monitoring multiple sessions in real-time |
| 26 | claude-code-analytics | [sujankapadia/claude-code-analytics](https://github.com/sujankapadia/claude-code-analytics) | Captures, archives, and analyzes conversations with interactive dashboard |
| 27 | Sniffly | [chiphuyen/sniffly](https://github.com/chiphuyen/sniffly) | Analyzes Claude Code logs to improve usage -- stats, error analysis, sharing |
| 28 | Claude Usage Analytics (VS Code) | [AnalyticEndeavorsUser/claude-usage-analytics](https://github.com/AnalyticEndeavorsUser/claude-usage-analytics) | VS Code extension: 4-tab dashboard, 7 status bar widgets, lifetime costs |

---

### Category 3: Prompt & Context Compression

Tools that compress prompts, context windows, or conversation history.

| # | Name | Repo | Description |
|---|------|------|-------------|
| 29 | LLMLingua | [microsoft/LLMLingua](https://github.com/microsoft/LLMLingua) | Microsoft's prompt compression, up to 20x compression, integrated into LangChain/LlamaIndex |
| 30 | prompt_compressor | [metawake/prompt_compressor](https://github.com/metawake/prompt_compressor) | Python library compressing prompts while preserving semantic meaning |
| 31 | token-optimizer-mcp | [ooples/token-optimizer-mcp](https://github.com/ooples/token-optimizer-mcp) | MCP server achieving 95%+ reduction through caching, compression, smart tool intelligence |
| 32 | token-optimizer | [alexgreensh/token-optimizer](https://github.com/alexgreensh/token-optimizer) | Finds ghost tokens, survives compaction, avoids context quality decay |
| 33 | claude-token-optimizer | [nadimtuhin/claude-token-optimizer](https://github.com/nadimtuhin/claude-token-optimizer) | Reusable CLAUDE.md setup for 90% token savings in 5 minutes |
| 34 | claude-token-efficient | [drona23/claude-token-efficient](https://github.com/drona23/claude-token-efficient) | Drop-in CLAUDE.md that reduces output verbosity on heavy workflows |
| 35 | Morph LLM | [morphllm.com](https://www.morphllm.com/) | Flash Compact drops 50-70% of context at 33K+ tokens/sec; model routing saves 40-70% |

---

### Category 4: Caching Proxies

Tools that cache LLM responses to avoid redundant API calls.

| # | Name | Repo | Description |
|---|------|------|-------------|
| 36 | GPTCache | [zilliztech/GPTCache](https://github.com/zilliztech/GPTCache) | Semantic cache using embedding similarity search; LangChain/LlamaIndex integration |
| 37 | Prompt Cache | [messkan/prompt-cache](https://github.com/messkan/prompt-cache) | Go proxy with semantic caching, up to 80% cost reduction, sub-ms responses |
| 38 | Semcache | [sensoris/semcache](https://github.com/sensoris/semcache) | Semantic caching with HTTP proxy mode, Prometheus metrics, built-in dashboard |
| 39 | SnackCache | [sodiumsun/snackcache](https://github.com/sodiumsun/snackcache) | Drop-in caching proxy for OpenAI/Anthropic APIs, one-line base URL change |
| 40 | Rubberduck | [Zipstack/rubberduck](https://github.com/Zipstack/rubberduck) | LLM caching proxy with failure simulation, rate limiting, per-user instances |
| 41 | llm_proxy | [robbyt/llm_proxy](https://github.com/robbyt/llm_proxy) | Go proxy with semantic + exact match caching, grounding, moderation, rate limiting |
| 42 | Cache-Cool | [MSNP1381/cache-cool](https://github.com/MSNP1381/cache-cool) | LLM caching with Redis, MongoDB, and JSON backends |

---

### Category 5: Model Routing & Load Balancing

Tools that route requests to different models based on complexity, cost, or availability.

| # | Name | Repo | Description |
|---|------|------|-------------|
| 43 | LiteLLM | [BerriAI/litellm](https://github.com/BerriAI/litellm) | SDK + proxy for 100+ LLMs, unified API, cost tracking, load balancing, caching (~40k stars) |
| 44 | Bifrost | [maximhq/bifrost](https://github.com/maximhq/bifrost) | Go-based AI gateway, 50x faster than LiteLLM, adaptive load balancing, semantic caching |
| 45 | Portkey Gateway | [portkey-ai/gateway](https://github.com/portkey-ai/gateway) | Enterprise AI gateway with semantic caching, guardrails, observability (~6k stars) |
| 46 | Claude Code Router | [musistudio/claude-code-router](https://github.com/musistudio/claude-code-router) | Routes requests to different models/providers with dynamic /model switching |
| 47 | Claude Router | [0xrdan/claude-router](https://github.com/0xrdan/claude-router) | Intelligent routing to optimal Claude model (Haiku/Sonnet/Opus), up to 80% savings |
| 48 | Claude Code Mux | [9j/claude-code-mux](https://github.com/9j/claude-code-mux) | Rust proxy with intelligent routing, provider failover, streaming, 15+ providers |
| 49 | ccproxy | [starbaser/ccproxy](https://github.com/starbaser/ccproxy) | Build mods for Claude Code: hook requests, modify responses, custom routing via LiteLLM |
| 50 | LLM Router | [ypollak2/llm-router](https://github.com/ypollak2/llm-router) | Auto-picks cheapest model per task, routes within subscription first, 70-85% savings |
| 51 | RelayPlane | [RelayPlane/proxy](https://github.com/RelayPlane/proxy) | Cost intelligence proxy with smart routing, dashboard, policy engine, 11 providers |
| 52 | ClawRouter | [BlockRunAI/ClawRouter](https://github.com/BlockRunAI/ClawRouter) | Agent-native router analyzing requests across 15 dimensions, <1ms routing |
| 53 | claude-code-proxy | [1rgs/claude-code-proxy](https://github.com/1rgs/claude-code-proxy) | Run Claude Code on OpenAI models via proxy translation |
| 54 | CLIProxyAPI | [router-for-me/CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) | Wraps Gemini CLI, Claude Code, Codex as unified API service |
| 55 | OpenRouter | [openrouter.ai](https://openrouter.ai/) | Auto-router selecting best model per prompt based on complexity |
| 56 | Claude Max API Proxy | [mattschwen/claude-max-api-proxy](https://github.com/mattschwen/claude-max-api-proxy) | Uses $200/mo Max subscription as OpenAI-compatible API endpoint |
| 57 | Meridian | [rynfar/meridian](https://github.com/rynfar/opencode-claude-max-proxy) | Bridges Claude Code SDK to standard Anthropic API with streaming and caching |

---

### Category 6: Session Management

Tools that manage Claude Code sessions, auto-compact, resume, track lifecycle.

| # | Name | Repo | Description |
|---|------|------|-------------|
| 58 | claude-sessions | [iannuttall/claude-sessions](https://github.com/iannuttall/claude-sessions) | Slash commands for comprehensive session tracking and documentation |
| 59 | claude-code-session-manager | [Divyanshubansaldb/claude-code-session-manager](https://github.com/Divyanshubansaldb/claude-code-session-manager) | Slash commands for session management |
| 60 | ccmanager | [kbwo/ccmanager](https://github.com/kbwo/ccmanager) | Multi-agent session manager for Claude Code, Gemini CLI, Codex CLI, Cursor, Copilot, Cline, OpenCode, Kimi |
| 61 | opcode | [winfunc/opcode](https://github.com/winfunc/opcode) | Tauri desktop app for managing sessions, custom agents, background agents, usage tracking |
| 62 | claude-session-manager (Swarek) | [Swarek/claude-session-manager](https://github.com/Swarek/claude-session-manager) | Smart multi-session with auto ID assignment, live status line, unlimited sessions |
| 63 | claude-session-manager (danilotorrisi) | [danilotorrisi/claude-session-manager](https://github.com/danilotorrisi/claude-session-manager) | CLI managing sessions using tmux and git worktrees |
| 64 | claude-session-management | [deemkeen/claude-session-management](https://github.com/deemkeen/claude-session-management) | Session snapshots with git versioning, export/import, auto-commit |
| 65 | claude-queue | [vasiliyk/claude-queue](https://github.com/vasiliyk/claude-queue) | Queue tasks with priorities/dependencies, monitors Plan limits, auto-pauses at capacity |
| 66 | claude-code-queue | [JCSnap/claude-code-queue](https://github.com/JCSnap/claude-code-queue) | Auto-queue instructions when rate limit resets, markdown-based queue with YAML frontmatter |
| 67 | claude-dashboard (TUI) | [Tpain166/claude-dashboard](https://github.com/Tpain166/claude-dashboard) | TUI with real-time monitoring, conversation history, automatic session detection |

---

### Category 7: Context Window & Memory Management

Tools that intelligently manage what goes into the context window across sessions.

| # | Name | Repo | Description |
|---|------|------|-------------|
| 68 | claude-mem | [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem) | Auto-captures everything Claude does, compresses with AI, injects relevant context via SQLite |
| 69 | context-memory | [ErebusEnigma/context-memory](https://github.com/ErebusEnigma/context-memory) | Persistent searchable context storage across sessions using SQLite + FTS5 |
| 70 | claude_memory | [codenamev/claude_memory](https://github.com/codenamev/claude_memory) | Long-term memory using hooks, MCP tools, SQLite, native vector storage (sqlite-vec) |
| 71 | claude-code-auto-memory | [severity1/claude-code-auto-memory](https://github.com/severity1/claude-code-auto-memory) | Automatically maintains CLAUDE.md files across sessions |
| 72 | mcp-memory-keeper | [mkreyman/mcp-memory-keeper](https://github.com/mkreyman/mcp-memory-keeper) | MCP server for cross-session context with knowledge graph, visualization, semantic search |

---

### Category 8: CLAUDE.md & System Prompt Optimization

Tools that help manage, optimize, or generate effective CLAUDE.md files and prompts.

| # | Name | Repo | Description |
|---|------|------|-------------|
| 73 | claude-md-optimizer | [wrsmith108/claude-md-optimizer](https://github.com/wrsmith108/claude-md-optimizer) | Skill for optimizing oversized CLAUDE.md using progressive disclosure with zero info loss |
| 74 | claude-code-prompt-optimizer | [johnpsasser/claude-code-prompt-optimizer](https://github.com/johnpsasser/claude-code-prompt-optimizer) | Hook that transforms simple prompts into structured instructions using Opus |
| 75 | prompt-architect | [ckelsoe/claude-skill-prompt-architect](https://github.com/ckelsoe/claude-skill-prompt-architect) | Transforms vague prompts into expert-level prompts using 7 frameworks (CO-STAR, RISEN, etc.) |
| 76 | claude-code-system-prompts | [Piebald-AI/claude-code-system-prompts](https://github.com/Piebald-AI/claude-code-system-prompts) | All parts of Claude Code's system prompt with token counts, updated per release |
| 77 | claude-code-prompts | [repowise-dev/claude-code-prompts](https://github.com/repowise-dev/claude-code-prompts) | Prompt templates for system prompts, tool prompts, agent delegation, memory |
| 78 | prompt-master | [nidhinjs/prompt-master](https://github.com/nidhinjs/prompt-master) | Skill that writes accurate prompts for any AI tool with zero wasted tokens |
| 79 | comfy-claude-prompt-library | [Comfy-Org/comfy-claude-prompt-library](https://github.com/Comfy-Org/comfy-claude-prompt-library) | Collection of Claude Code commands and memories for agentic coding |
| 80 | claude-md-templates | [abhishekray07/claude-md-templates](https://github.com/abhishekray07/claude-md-templates) | CLAUDE.md best practices and template collection |

---

### Category 9: Agent Orchestration

Tools that orchestrate multiple Claude instances or manage subagent spawning.

| # | Name | Repo | Description |
|---|------|------|-------------|
| 81 | claude-squad | [smtg-ai/claude-squad](https://github.com/smtg-ai/claude-squad) | Manage multiple AI agents (Claude Code, Codex, OpenCode, Amp) in tmux with TUI and worktree isolation |
| 82 | ruflo (claude-flow) | [ruvnet/ruflo](https://github.com/ruvnet/ruflo) | Multi-agent swarms, autonomous workflows, RAG integration, 313 MCP tools |
| 83 | claude_code_agent_farm | [Dicklesworthstone/claude_code_agent_farm](https://github.com/Dicklesworthstone/claude_code_agent_farm) | Run 20+ Claude Code agents in parallel with lock-based coordination, tmux monitoring |
| 84 | metaswarm | [dsifry/metaswarm](https://github.com/dsifry/metaswarm) | Self-improving multi-agent framework, 18 agents, 13 skills, 15 commands, TDD enforcement |
| 85 | claude-code-workflow-orchestration | [barkain/claude-code-workflow-orchestration](https://github.com/barkain/claude-code-workflow-orchestration) | Hook-based workflow orchestration with task decomposition and parallel execution |
| 86 | parallel-code | [johannesjo/parallel-code](https://github.com/johannesjo/parallel-code) | Desktop app giving every AI agent its own git branch and worktree automatically |
| 87 | agent-of-empires | [njbrake/agent-of-empires](https://github.com/njbrake/agent-of-empires) | Terminal session manager for Claude Code, OpenCode, Codex CLI via tmux and git worktrees |
| 88 | agent-deck | [asheshgoplani/agent-deck](https://github.com/asheshgoplani/agent-deck) | Terminal session manager TUI for Claude, Gemini, OpenCode, Codex |
| 89 | ntm | [Dicklesworthstone/ntm](https://github.com/Dicklesworthstone/ntm) | Spawn, tile, and coordinate multiple AI coding agents across tmux panes |
| 90 | claude-code-hooks-multi-agent-observability | [disler/claude-code-hooks-multi-agent-observability](https://github.com/disler/claude-code-hooks-multi-agent-observability) | Real-time monitoring for Claude Code agents through hook event tracking |

---

### Category 10: Plugins, Skills & Marketplaces

Community plugins, skills, and curated collections.

| # | Name | Repo | Description |
|---|------|------|-------------|
| 91 | SkillKit | [rohitg00/skillkit](https://github.com/rohitg00/skillkit) | Package manager for AI agent skills across Claude Code, Cursor, Codex, Copilot, 40+ agents |
| 92 | OpenSkills | [numman-ali/openskills](https://github.com/numman-ali/openskills) | Universal skills loader for AI coding agents (npm i -g openskills) |
| 93 | awesome-claude-code-toolkit | [rohitg00/awesome-claude-code-toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit) | 135 agents, 35 skills, 42 commands, 150+ plugins, 19 hooks |
| 94 | claude-skills (220+) | [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | 220+ skills for engineering, marketing, product, compliance |
| 95 | antigravity-awesome-skills | [sickn33/antigravity-awesome-skills](https://github.com/sickn33/antigravity-awesome-skills) | 1,370+ agentic skills with installer CLI, bundles, workflows |
| 96 | claude-code-skill-factory | [alirezarezvani/claude-code-skill-factory](https://github.com/alirezarezvani/claude-code-skill-factory) | Toolkit for building and deploying production-ready skills at scale |
| 97 | claude-marketplace | [dashed/claude-marketplace](https://github.com/dashed/claude-marketplace) | Local marketplace for personal Claude Code skills and plugins |
| 98 | claude-code-skills marketplace | [daymade/claude-code-skills](https://github.com/daymade/claude-code-skills) | 43 production-ready professional skills |
| 99 | everything-claude-code | [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code) | Agent harness optimization with skills, instincts, memory, security |
| 100 | claude-code-hooks-mastery | [disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery) | Master Hooks with UV single-file Python scripts in .claude/hooks/ |
| 101 | Anthropic official skills | [anthropics/skills](https://github.com/anthropics/skills) | Official public repository for Agent Skills from Anthropic |
| 102 | awesome-claude-code | [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | Curated list of skills, hooks, slash-commands, orchestrators, plugins |
| 103 | awesome-claude-code-plugins | [ccplugins/awesome-claude-code-plugins](https://github.com/ccplugins/awesome-claude-code-plugins) | Curated list of slash commands, subagents, MCP servers, hooks |
| 104 | awesome-claude-plugins (Composio) | [ComposioHQ/awesome-claude-plugins](https://github.com/ComposioHQ/awesome-claude-plugins) | Curated list of plugins extending Claude Code |

---

### Category 11: MCP Server Management

Tools for managing, installing, or optimizing MCP servers.

| # | Name | Repo | Description |
|---|------|------|-------------|
| 105 | mcp-installer | [anaisbetts/mcp-installer](https://github.com/anaisbetts/mcp-installer) | MCP server that installs other MCP servers from npm or PyPI |
| 106 | mcp-manager | [MediaPublishing/mcp-manager](https://github.com/MediaPublishing/mcp-manager) | Web GUI for managing MCP servers in Claude and Cursor with enable/disable toggle |
| 107 | mcp-server-manager | [infinitimeless/mcp-server-manager](https://github.com/infinitimeless/mcp-server-manager) | Create, build, and manage MCP servers for Claude and other clients |
| 108 | mcpx | [kwonye/mcpx](https://github.com/kwonye/mcpx) | Universal MCP server manager -- install once, auth once, sync to every AI tool |
| 109 | mcp-hub | [ravitemer/mcp-hub](https://github.com/ravitemer/mcp-hub) | Centralized manager with dynamic monitoring; clients connect to one endpoint |
| 110 | modelcontextprotocol/servers | [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) | Official collection of Model Context Protocol servers |

---

### Category 12: Security & Audit

Tools that audit sessions for security issues, PII leaks, or unsafe operations.

| # | Name | Repo | Description |
|---|------|------|-------------|
| 111 | Gryph | [safedep/gryph](https://github.com/safedep/gryph) | Security layer for AI agents; hooks, logs file reads/writes/commands to SQLite |
| 112 | AgentGuard | [GoPlusSecurity/agentguard](https://github.com/GoPlusSecurity/agentguard) | Real-time security: scans skills, blocks dangerous actions, daily patrols, 24 detection rules |
| 113 | Agent Audit | [HeadyZhang/agent-audit](https://github.com/HeadyZhang/agent-audit) | Static scanner for prompt injection, MCP config auditing, 49 rules mapped to OWASP Agentic Top 10 |
| 114 | Ship Safe | [asamassekou10/ship-safe](https://github.com/asamassekou10/ship-safe) | CLI scanner: CI/CD misconfigs, agent permission risks, MCP injection, secrets, DMCA issues |
| 115 | agent-security (MintMCP) | [mintmcp/agent-security](https://github.com/mintmcp/agent-security) | Hooks for secrets scanning -- standalone, local-first, regex-only |
| 116 | claude-code-security-review | [anthropics/claude-code-security-review](https://github.com/anthropics/claude-code-security-review) | Official Anthropic GitHub Action for security analysis on PRs |
| 117 | code-audit | [evilsocket/code-audit](https://github.com/evilsocket/code-audit) | AI agent performing security audits, saves findings to AUDIT.md |
| 118 | Promptfoo | [promptfoo/promptfoo](https://github.com/promptfoo/promptfoo) | Red teaming / pentesting / vulnerability scanning for AI, 50+ types (~5k stars) |
| 119 | claude-code-guardrails | [rulebricks/claude-code-guardrails](https://github.com/rulebricks/claude-code-guardrails) | Real-time guardrails for tool calls via PreToolUse hooks |
| 120 | Claude-Code-Guardrails | [wangbooth/Claude-Code-Guardrails](https://github.com/wangbooth/Claude-Code-Guardrails) | Branch protection, automatic checkpointing, safe commit squashing |

---

### Category 13: Budget & Rate Limit Management

Tools that enforce spending limits, rate limiting, or quota management.

| # | Name | Repo | Description |
|---|------|------|-------------|
| 121 | AgentBudget | [sahiljagtap08/agentbudget](https://github.com/sahiljagtap08/agentbudget) | "ulimit for AI agents" -- hard dollar limits per session, automatic circuit breaking |
| 122 | llm-budget | [Mattbusel/llm-budget](https://github.com/Mattbusel/llm-budget) | Fleet-level cost governance: daily, per-request, per-agent, rolling-window policies |
| 123 | llm-proxy (Instawork) | [Instawork/llm-proxy](https://github.com/Instawork/llm-proxy) | Go reverse proxy with cost tracking and rate limiting, 429 with Retry-After headers |
| 124 | LLM-API-Key-Proxy | [Mirrowel/LLM-API-Key-Proxy](https://github.com/Mirrowel/LLM-API-Key-Proxy) | Universal gateway with multi-provider translation and load-balancing |
| 125 | llm-rate-limiter | [jacobphillips99/llm-rate-limiter](https://github.com/jacobphillips99/llm-rate-limiter) | Python package for rate limits with monitoring and visualization |
| 126 | UsagePanda Proxy | [usagepanda/proxy](https://github.com/usagepanda/proxy) | Lightweight proxy enforcing security, cost, rate limiting, policy controls |

---

### Category 14: LLM Observability Platforms

Full-stack observability platforms with tracing, cost analytics, and evaluation.

| # | Name | Repo | Description |
|---|------|------|-------------|
| 127 | Langfuse | [langfuse/langfuse](https://github.com/langfuse/langfuse) | Open-source LLM engineering platform with tracing, cost analytics, prompt management (~21k stars) |
| 128 | Helicone | [Helicone/helicone](https://github.com/Helicone/helicone) | Open-source LLM observability with one-line integration (~3k+ stars) |
| 129 | Arize Phoenix | [Arize-ai/phoenix](https://github.com/Arize-ai/phoenix) | OpenTelemetry-native AI observability and evaluation (~7.8k stars) |
| 130 | Opik | [comet-ml/opik](https://github.com/comet-ml/opik) | Open-source tracing, cost tracking, evaluation metrics, prompt management (Apache 2.0) |
| 131 | Prompt Sail | [PromptSail/prompt_sail](https://github.com/PromptSail/prompt_sail) | Proxy capturing all API interactions with cost analysis and trend tracking |
| 132 | claude-code-otel | [ColeMurray/claude-code-otel](https://github.com/ColeMurray/claude-code-otel) | OpenTelemetry observability for Claude Code with Grafana dashboards |
| 133 | claude-code-monitor | [zcquant/claude-code-monitor](https://github.com/zcquant/claude-code-monitor) | OTLP-based real-time token usage tracking and cost analytics dashboard |

---

### Category 15: Configuration & Sync

Tools for managing Claude Code settings across machines, teams, or projects.

| # | Name | Repo | Description |
|---|------|------|-------------|
| 134 | CCMS | [miwidot/ccms](https://github.com/miwidot/ccms) | Bash script syncing ~/.claude/ between machines via rsync over SSH |
| 135 | Claude Setting Manager | [shyinlim/claude_setting_manager](https://github.com/shyinlim/claude_setting_manager) | Centralized CLAUDE.md management for teams -- distribute config templates |
| 136 | claude-code-sync | [porkchop/claude-code-sync](https://github.com/porkchop/claude-code-sync) | Sync conversations across devices (projects, edit history, todos, commands) |
| 137 | cclint | [carlrannaberg/cclint](https://github.com/carlrannaberg/cclint) | Linter for Claude Code project files: validates commands, hooks, CLAUDE.md best practices |
| 138 | claude-rules | [lifedever/claude-rules](https://github.com/lifedever/claude-rules) | Auto-detect tech stack, generate project rules for Claude Code, Cursor, Copilot |
| 139 | claude-code-templates | [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) | CLI for configuring Claude Code with ready-to-use agents, commands, settings, hooks |

---

### Category 16: Workflow Automation & CI/CD

Tools that automate common workflows (git ops, PR review, testing, deployment).

| # | Name | Repo | Description |
|---|------|------|-------------|
| 140 | claude-code-action | [anthropics/claude-code-action](https://github.com/anthropics/claude-code-action) | Official GitHub Action: @claude in PRs/issues triggers analysis and implementation |
| 141 | Claude-Code-Workflow | [catlog22/Claude-Code-Workflow](https://github.com/catlog22/Claude-Code-Workflow) | JSON-driven multi-agent development framework with CLI orchestration |
| 142 | claude-code-spec-workflow | [Pimzino/claude-code-spec-workflow](https://github.com/Pimzino/claude-code-spec-workflow) | Spec-driven: Requirements -> Design -> Tasks -> Implementation pipeline |
| 143 | claude-code-workflows (OneRedOak) | [OneRedOak/claude-code-workflows](https://github.com/OneRedOak/claude-code-workflows) | Battle-tested workflows from an AI-native startup |
| 144 | CodeRabbit | [coderabbit.ai](https://www.coderabbit.ai/) | Most adopted AI review app on GitHub/GitLab (2M+ repos), 40+ analyzers |
| 145 | Greptile | [greptile.com](https://www.greptile.com/) | Indexes repos into knowledge graph for deep PR analysis, 82% bug catch rate |
| 146 | Qodo PR-Agent | [qodo-ai/pr-agent](https://github.com/qodo-ai/pr-agent) | Open-source PR reviewer with multi-agent architecture and test generation |
| 147 | GPTLint | [gptlint/gptlint](https://github.com/gptlint/gptlint) | LLM-powered linter enforcing higher-level best practices with markdown rules |

---

### Category 17: Alternative & Complementary Coding Agents

Other AI coding agents that can work alongside or replace Claude Code for specific tasks.

| # | Name | Repo / URL | Description |
|---|------|------------|-------------|
| 148 | Aider | [aider-ai/aider](https://github.com/aider-ai/aider) | Terminal AI pair programmer with Git integration, auto-commits (~25k stars) |
| 149 | Cline | [cline/cline](https://github.com/cline/cline) | Autonomous VS Code coding assistant with Plan/Act modes (5M+ devs) |
| 150 | Continue | [continuedev/continue](https://github.com/continuedev/continue) | Open-source IDE extension for custom AI assistants (20k+ stars) |
| 151 | Cursor | [cursor.com](https://www.cursor.com/) | AI-augmented IDE with agent mode and Background Agents ($20/mo) |
| 152 | Roo Code | [RooCodeInc/Roo-Code](https://github.com/RooCodeInc/Roo-Code) | Full dev team of AI agents in your editor, multi-file edits, tests, browser |
| 153 | Kilo Code | [Kilo-Org/kilocode](https://github.com/Kilo-Org/kilocode) | Superset of Roo Code + Cline, #1 on OpenRouter, 1.5M+ users |
| 154 | OpenCode | [opencode.ai](https://opencode.ai/) | Terminal agent with LSP integration, multi-session (120k+ stars) |
| 155 | Gemini CLI | [google/gemini-cli](https://github.com/google/gemini-cli) | Google's terminal agent, free tier: 60 req/min, 1000 req/day |
| 156 | Goose | [block/goose](https://github.com/block/goose) | Open-source AI agent framework by Block, runs locally, extensible |
| 157 | Windsurf | [windsurf.com](https://windsurf.com/) | VS Code fork by Codeium with Cascade agentic flows ($15/mo) |
| 158 | Augment Code | [augmentcode.com](https://www.augmentcode.com/) | Deep context engine for large codebases, excels at big refactoring |
| 159 | Zed Editor | [zed.dev](https://zed.dev/ai) | Rust-powered IDE with built-in agentic workflows and multi-agent support |

---

### Category 18: GUI Wrappers & Desktop Apps

Desktop interfaces for Claude Code.

| # | Name | Repo | Description |
|---|------|------|-------------|
| 160 | claudecodeui (CloudCLI) | [siteboon/claudecodeui](https://github.com/siteboon/claudecodeui) | Open-source web UI for managing sessions remotely on mobile and desktop |
| 161 | simple-code-gui | [DonutsDelivery/simple-code-gui](https://github.com/DonutsDelivery/simple-code-gui) | Desktop app with sidebar, tabs, workspace persistence |
| 162 | claude-code-desktop | [hsiaol/claude-code-desktop](https://github.com/hsiaol/claude-code-desktop) | Desktop GUI wrapper for Claude Code CLI |
| 163 | CodePilot | [op7418/CodePilot](https://github.com/op7418/CodePilot) | Multi-model AI agent desktop client with MCP and skills (Electron + Next.js) |
| 164 | Claudia GUI | [claudia.so](https://claudia.so/) | Open-source visual interface for Claude Code |

---

### Summary

| Category | Count |
|----------|-------|
| CLI Output Compression & Filtering | 8 |
| Token & Cost Monitoring | 20 |
| Prompt & Context Compression | 7 |
| Caching Proxies | 7 |
| Model Routing & Load Balancing | 15 |
| Session Management | 10 |
| Context Window & Memory Management | 5 |
| CLAUDE.md & Prompt Optimization | 8 |
| Agent Orchestration | 10 |
| Plugins, Skills & Marketplaces | 14 |
| MCP Server Management | 6 |
| Security & Audit | 10 |
| Budget & Rate Limit Management | 6 |
| LLM Observability Platforms | 7 |
| Configuration & Sync | 6 |
| Workflow Automation & CI/CD | 7 |
| Alternative Coding Agents | 12 |
| GUI Wrappers & Desktop Apps | 5 |
| **Total** | **163** |
