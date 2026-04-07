```
  ██████╗ ██████╗       ███╗   ███╗  █████╗  ███╗  ██╗  █████╗   ██████╗ ███████╗██████╗
 ██╔════╝██╔════╝      ████╗ ████║██╔══██╗████╗ ██║██╔══██╗██╔════╝ ██╔════╝██╔══██╗
 ██║     ██║           ██╔████╔██║███████║██╔██╗██║███████║██║  ███╗█████╗  ██████╔╝
 ██║     ██║           ██║╚██╔╝██║██╔══██║██║╚████║██╔══██║██║   ██║██╔══╝  ██╔══██╗
 ╚██████╗╚██████╗      ██║ ╚═╝ ██║██║  ██║██║ ╚███║██║  ██║╚██████╔╝███████╗██║  ██║
  ╚═════╝ ╚═════╝      ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚══╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝
```

**Claude Code Ecosystem Controller**

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square)
![License MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![152 tools](https://img.shields.io/badge/Registry-152%20tools-cyan?style=flat-square)
![TDD](https://img.shields.io/badge/Tests-439%20passing-brightgreen?style=flat-square)

---

## What is it?

cc-manager is **"pnpm for Claude Code"** — one command to set up your entire Claude Code environment. It installs tools from a curated registry of 152 entries, wires session hooks, tracks usage across every session, and surfaces insights through analytics and a visual dashboard. It is a standalone CLI, not a plugin — it configures Claude Code and then stays out of the way.

---

## Quick Start

```bash
# Install
uv tool install cc-manager
# or
pipx install cc-manager

# Interactive setup (detects your env, installs recommended tools, wires hooks)
ccm init

# Verify everything is wired correctly
ccm status
```

---

## `ccm init` — the setup experience

Five-step interactive setup. Idempotent — safe to re-run at any time.

```
$ ccm init

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
  [9/10] repomix ........... not found. Install? [Y/n] y
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

Done. Run `ccm status` to verify.
```

**Flags:**

| Flag | Effect |
|---|---|
| `--yes` | Non-interactive. Installs all recommended tools, enables all modules. |
| `--minimal` | Enables cc-later modules only. No external tools. |
| `--dry-run` | Print what would change without writing any files. |

---

## Command Reference

### Setup & Management

| Command | Description |
|---|---|
| `ccm init` | Interactive setup: detect env, install tools, wire hooks |
| `ccm status` | Mission control: all tools, hooks, last session |
| `ccm doctor` | System diagnostic: validate everything |
| `ccm uninstall` | Clean removal of all cc-manager config |

### Tool Registry (152 tools)

| Command | Description |
|---|---|
| `ccm install <tool>` | Install from registry |
| `ccm remove <tool>` | Remove tool + clean settings.json |
| `ccm list` | Browse registry with tiers |
| `ccm list --installed` | Show installed tools |
| `ccm list --category=mcp-server` | Filter by category |
| `ccm search <query>` | Fuzzy search registry |
| `ccm info <tool>` | Full tool details |
| `ccm update` | Update all outdated tools |
| `ccm update <tool>` | Update specific tool |
| `ccm outdated` | Show what needs updating |
| `ccm pin <tool>` | Pin tool version |
| `ccm unpin <tool>` | Unpin tool |

### Config & Backup

| Command | Description |
|---|---|
| `ccm backup create` | Snapshot settings.json |
| `ccm backup list` | List all backups |
| `ccm backup restore <ts>` | Restore from backup |
| `ccm config get <key>` | Read config value |
| `ccm config set <key> <value>` | Update config |
| `ccm config edit` | Open in $EDITOR |
| `ccm diff` | Show settings.json changes since last backup |
| `ccm audit` | Ownership report: what owns what in settings.json |
| `ccm why <tool>` | Trace when/how a tool was installed |

### Analytics

| Command | Description |
|---|---|
| `ccm analyze` | Token/cost breakdown, last 7d |
| `ccm analyze --period=30d` | Custom period |
| `ccm recommend` | Tool suggestions based on usage |
| `ccm logs` | Event stream |
| `ccm logs --event=session_end` | Filter events |

### Portability

| Command | Description |
|---|---|
| `ccm export` | Export setup to JSON |
| `ccm import <file>` | Import setup (great for onboarding) |
| `ccm migrate` | Upgrade config schema |
| `ccm reset <tool>` | Reinstall a tool |

### Extras

| Command | Description |
|---|---|
| `ccm serve [--port=9847]` | Local JSON API |
| `ccm dashboard` | Cyberpunk visual dashboard |
| `ccm clean --sessions` | Clean old session data |
| `ccm completions zsh` | Shell completions |

Every mutating command supports `--dry-run`.

---

## Tool Registry

152 tools across 20 categories: `analytics`, `ci-cd`, `code-review`, `config`, `context`, `docker`, `hooks`, `ide`, `integration`, `mcp-server`, `memory`, `observability`, `orchestration`, `security`, `session`, `skills`, `task-management`, `terminal-ui`, `voice`, `workflow`.

### Tiers

| Tier | Count | When you see it |
|---|---|---|
| `recommended` | 12 | Prompted during `ccm init` |
| `popular` | 47 | Visible via `ccm list` |
| `community` | 93 | Full catalog, `ccm search` |

### Recommended tools

| Tool | Category | Description |
|---|---|---|
| `rtk` | analytics | Token-optimized CLI proxy, 60-90% savings on dev operations |
| `ccusage` | analytics | Usage analytics CLI for Claude Code |
| `context7` | mcp-server | Version-specific library docs MCP server |
| `playwright-mcp` | mcp-server | Browser automation via MCP |
| `claude-squad` | orchestration | Multi-agent tmux orchestration TUI |
| `agnix` | config | Config linter for Claude Code (385 rules) |
| `trail-of-bits` | security | Security-focused auditing skills |
| `claude-code-action` | ci-cd | GitHub Actions CI/CD for Claude Code |
| `repomix` | context | Pack your entire codebase into a single AI-friendly file |
| `superpowers` | skills | Structured dev lifecycle skills |
| `code-review-graph` | code-review | Visual code review dependency graphs |
| `mcp-memory-keeper` | memory | Long-term memory MCP server |

```bash
# Browse by category
ccm list --category=mcp-server
ccm list --category=orchestration

# Search
ccm search memory
ccm search "github actions"

# Install anything
ccm install repomix
ccm install claude-swarm
```

---

## Analytics

`ccm analyze` reads the append-only event log at `~/.cc-manager/store/events.jsonl` and renders a breakdown of your Claude Code usage.

```
$ ccm analyze --period=7d

╔══════════════════════════════════════════════════════════╗
║  USAGE ANALYSIS  ·  Last 7d                              ║
╚══════════════════════════════════════════════════════════╝

  Total Cost        $8.12          Total Tokens    12.2M
  Sessions          47             Avg Duration    38.4 min
  Input Tokens      9.8M           Output Tokens   2.4M
  Cache Read        7.2M           Compactions     12

⚡ MODEL BREAKDOWN
  claude-sonnet  ████████████████████░░░░  85%   $4.90
  claude-opus    ████░░░░░░░░░░░░░░░░░░░░  15%   $3.22

⚡ TOP BASH COMMANDS
  COMMAND              USES
  git                    94
  npm                    71
  pytest                 58
  cargo                  42
```

Customize the analysis period with `--period=24h`, `--period=30d`, etc. Output as JSON with `--json` for scripting.

---

## Dashboard

```bash
ccm dashboard
# Opens http://localhost:9847 in your browser
```

Real-time cyberpunk dashboard powered by Chart.js. Displays token burn rate, cost trends, session history, tool health panel, and recommendations. All data is local — nothing leaves your machine.

Serve headlessly for scripting:

```bash
ccm serve --port=9847
# GET /api/status
# GET /api/analyze?period=7d
# GET /api/tools
```

---

## How it works

cc-manager is a **standalone CLI**, not a runtime plugin. When you run `ccm init`, it:

1. Detects your Claude Code installation at `~/.claude/`
2. Merges hook entries into `~/.claude/settings.json` (never overwrites, never touches non-cc-manager entries)
3. Installs `~/.cc-manager/dispatch.py` as the single hook entry point
4. Deploys bundled cc-later modules under `~/.cc-manager/modules/`

From that point forward, Claude Code fires the hooks on its own. cc-manager is not running — it passively collects session data through the dispatcher. You invoke `ccm` explicitly to read that data, manage tools, or check status.

**What cc-manager writes:**

| Path | What it does | Reversible |
|---|---|---|
| `~/.claude/settings.json` | Merges hook entries + MCP server configs | Yes (backup + targeted removal) |
| `~/.claude/CLAUDE.md` | Appends one line: `@cc-manager` | Yes (remove that line) |
| `~/.claude/cc-manager.md` | Instructions file referenced by CLAUDE.md | Yes (`rm`) |
| `~/.claude/skills/cc-manager/` | Skill definitions for built-in modules | Yes (`rm -r`) |
| `~/.cc-manager/` | cc-manager home: config, registry, event log, backups | Yes (`ccm uninstall`) |

**What cc-manager never touches:**

- Non-cc-manager hook entries (rtk, plugins, user hooks)
- `enabledPlugins`, `allowedTools`, or other settings.json fields
- Project-level `.claude/` directories
- `history.jsonl`, `sessions/`, or any Claude Code internal state

---

## Configuration

`~/.cc-manager/cc-manager.toml` — single config file. Edit with `ccm config edit`.

```toml
[manager]
version = "0.1.0"
backup_on_change = true     # Auto-backup before any settings.json modification
log_level = "info"          # debug | info | warn | error

[later]
enabled = true
max_entries_per_dispatch = 3
model = "sonnet"

[budget]
enabled = true
weekly_budget_tokens = 10_000_000
backoff_at_pct = 80

[window]
enabled = true
duration_minutes = 300

[stats]
enabled = true
cost_tracking = true

[stats.pricing]
# Per 1M tokens, USD — update when Anthropic changes pricing
sonnet_input = 3.00
sonnet_output = 15.00
opus_input = 15.00
opus_output = 75.00
haiku_input = 0.25
haiku_output = 1.25

[nudge]
enabled = true
stale_minutes = 10
max_retries = 2
```

**Config resolution order:**

1. Environment variables: `CC_MANAGER_<SECTION>_<KEY>` (e.g., `CC_MANAGER_LATER_ENABLED=false`)
2. `~/.cc-manager/cc-manager.toml`
3. Built-in defaults

---

## Built-in Modules (cc-later)

cc-manager bundles cc-later as its core module system. Each module runs independently in the dispatcher — if one crashes, others still fire.

| Module | Hook event | What it does |
|---|---|---|
| `later` | Stop | Dispatch queued tasks from `.claude/LATER.md` at window end |
| `compact` | SessionStart | Recover context after compaction events |
| `resume` | SessionStart | Auto-resume tasks that hit context limits |
| `budget` | PreToolUse | Enforce weekly token budget, backoff at threshold |
| `window` | Stop | Track 5-hour window lifecycle, compute time remaining |
| `stats` | SessionEnd | Collect token counts, cost, model, duration per session |
| `nudge` | Stop | Detect stale agents and restart them |

Toggle any module without touching settings.json:

```bash
ccm module later disable
ccm module budget enable
ccm module stats status
```

---

## Development

```bash
git clone https://github.com/your-org/cc-manager
cd cc-manager
uv sync --dev
pytest tests/ -v          # 439 tests
pytest tests/ --cov       # with coverage
```

**Runtime dependencies (3 total):**

| Package | Purpose |
|---|---|
| `typer>=0.14.0` | CLI framework |
| `rich>=13.0.0` | Tables, panels, progress bars, colors |
| `tomli-w>=1.0.0` | TOML writing (stdlib `tomllib` is read-only) |

Everything else — TOML reading, file locking, HTTP, JSON diffing, duration parsing — uses Python stdlib.

**Project layout:**

```
cc-manager/
├── cc_manager/
│   ├── cli.py              # Typer app + command registration
│   ├── context.py          # Paths, loaders, shared context
│   ├── store.py            # Append-only event log
│   ├── settings.py         # settings.json lock/read/write/backup
│   ├── commands/           # One file per command (~15-70 lines each)
│   ├── handlers/           # Hook event handlers
│   └── dashboard/          # Static files (index.html, style.css, app.js)
└── registry/
    └── tools.json          # 152-tool catalog, ships with the package
```

---

## License

MIT
