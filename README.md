```
  ██████╗ ██████╗       ███╗   ███╗  █████╗  ███╗  ██╗  █████╗   ██████╗ ███████╗██████╗
 ██╔════╝██╔════╝      ████╗ ████║██╔══██╗████╗ ██║██╔══██╗██╔════╝ ██╔════╝██╔══██╗
 ██║     ██║           ██╔████╔██║███████║██╔██╗██║███████║██║  ███╗█████╗  ██████╔╝
 ██║     ██║           ██║╚██╔╝██║██╔══██║██║╚████║██╔══██║██║   ██║██╔══╝  ██╔══██╗
 ╚██████╗╚██████╗      ██║ ╚═╝ ██║██║  ██║██║ ╚███║██║  ██║╚██████╔╝███████╗██║  ██║
  ╚═════╝ ╚═════╝      ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚══╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝
```

**Opinionated Claude Code Ecosystem Controller**

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square)
![License MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![35 tools](https://img.shields.io/badge/Registry-35%20curated%20tools-cyan?style=flat-square)
![148 tests](https://img.shields.io/badge/Tests-148%20passing-brightgreen?style=flat-square)

---

## What is it?

One command to set up your entire Claude Code environment. cc-manager installs tools from a curated registry of 35 entries (19 recommended, 8 popular, 8 community), wires session hooks, tracks token usage and cost across every session, and surfaces data-driven recommendations to cut waste.

It is a standalone CLI, not a plugin. It configures Claude Code and stays out of the way.

---

## Quick Start

```bash
# Install
pip install git+https://github.com/vaddisrinivas/cc-manager.git

# Interactive setup (detects env, installs tools, wires hooks)
ccm init

# Verify
ccm status

# Full-screen dashboard
ccm tui
```

`ccm init` flags: `--yes` (non-interactive), `--minimal` (hooks + config only), `--dry-run` (preview).

---

## Commands

### Setup

| Command | What it does |
|---|---|
| `ccm init` | 5-step setup: detect env, backup, install tools, enable modules, write config |
| `ccm status` | Installed tools, hook count, last session stats |
| `ccm doctor` | Full diagnostic: Python, config, store, hooks, tool detection |
| `ccm uninstall` | Clean removal of all cc-manager config |

### Tools

| Command | What it does |
|---|---|
| `ccm install <tool>` | Install from the curated registry |
| `ccm remove <tool>` | Remove tool + clean settings.json |
| `ccm list` | Browse registry by tier |
| `ccm list --installed` | Show what's installed |
| `ccm search <query>` | Fuzzy search the registry |

### Analytics

| Command | What it does |
|---|---|
| `ccm analyze` | Token/cost breakdown (last 7 days) |
| `ccm analyze --period=30d` | Custom period |
| `ccm recommend` | Data-driven tool suggestions |
| `ccm logs` | Event stream |
| `ccm tui` | Full-screen Textual dashboard |

### Config

| Command | What it does |
|---|---|
| `ccm config-get <key>` | Read config value (dot notation) |
| `ccm config-set <key> <val>` | Set config value |
| `ccm config-edit` | Open in $EDITOR |
| `ccm backup create` | Snapshot settings.json |
| `ccm backup list` | List backups |
| `ccm backup restore <ts>` | Restore from backup |

---

## Registry (35 tools)

Curated for one mission: **lower cost, save tokens, sharper sessions.**

### Recommended (19)

| Tool | Category | What it does |
|---|---|---|
| `rtk` | token-optimization | CLI proxy, 60-90% token savings |
| `cc-sentinel` | cost | Real-time waste interception |
| `cc-later` | session | Queues tasks, dispatches near window expiry |
| `cc-retrospect` | session | Post-session analytics and habit insights |
| `cc-budget` | cost | Per-prompt spending limits and pacing |
| `ccusage` | analytics | Usage analytics CLI |
| `context7` | mcp-server | Version-accurate library docs |
| `playwright-mcp` | mcp-server | Browser automation via MCP |
| `claude-squad` | orchestration | Multi-agent tmux TUI |
| `trail-of-bits` | security | Security auditing skills |
| `claude-code-action` | ci-cd | GitHub Actions for Claude Code |
| `repomix` | context | Pack codebase into AI-friendly file |
| `superclaude` | skills | Structured dev lifecycle skills |
| `claudekit` | skills | Community skill collection |
| `caveman` | skills | Output compression (~75% reduction) |
| `chrome-devtools-mcp` | mcp-server | Chrome DevTools via MCP |
| `serena` | mcp-server | Code-aware LSP MCP server |
| `wcgw` | mcp-server | Shell + code editing MCP |
| `github-mcp` | mcp-server | GitHub API via MCP |

### Popular (8) & Community (8)

`cc-memory`, `cc-retro`, `cc-compact`, `cc-score`, `cc-learning-hooks`, `cc-profiles`, `cc-context-watch`, `claude-swarm`, `claude-task-master`, `claude-mem`, `container-use`, `claude-devtools`, `sequential-thinking`, `desktop-commander`, `firecrawl-mcp`, `semgrep`

```bash
ccm search memory
ccm list --installed
ccm install claude-squad
```

---

## Recommendations

`ccm recommend` only fires when your data justifies it:

| Trigger | Recommendation |
|---|---|
| Avg > 500K tokens/session | `rtk` (token filter) |
| Compactions > sessions | `rtk` (context pressure) |
| Opus > 50% of sessions | Switch to Sonnet (5x cheaper) |
| Cost > $1/week | `cc-sentinel` (waste interception) |
| Cost > $2/week | `cc-budget` (spending limits) |
| No MCP servers | `context7` (doc injection) |
| Avg output > 200K/session | `caveman` (output compression) |
| 5+ sessions recorded | `cc-retrospect` (habit insights) |

No sessions recorded = no recommendations. No "you should install X" noise.

---

## TUI Dashboard

```bash
ccm tui
```

Full-screen Textual app with live widgets: token sparkline, cost breakdown by model, installed tools table, session history, health checks, and recommendations. Press `Q` to quit, `R` to refresh.

---

## How it Works

`ccm init` writes hook entries into `~/.claude/settings.json` so Claude Code fires events to `~/.cc-manager/hook.py`. The hook dispatcher routes events to handler modules. cc-manager itself is not running between invocations.

**What it writes:**

| Path | Purpose |
|---|---|
| `~/.claude/settings.json` | Hook entries + MCP configs (merged, never overwrites) |
| `~/.claude/CLAUDE.md` | Appends `@cc-manager` |
| `~/.claude/skills/cc-manager/` | Skill definitions |
| `~/.cc-manager/` | Config, registry, event log, backups |

**What it never touches:** non-cc-manager hooks, project-level `.claude/`, Claude Code internal state.

---

## Skills

cc-manager registers slash commands usable inside Claude Code sessions:

- `/cc-manager:status` `/cc-manager:install <tool>` `/cc-manager:remove <tool>`
- `/cc-manager:doctor` `/cc-manager:analyze` `/cc-manager:recommend` `/cc-manager:logs`
- `/cc-retrospect:cost` `/cc-retrospect:habits` `/cc-retrospect:health` `/cc-retrospect:waste` `/cc-retrospect:tips` `/cc-retrospect:compare` `/cc-retrospect:report` `/cc-retrospect:hints`
- `/cc-later:queue <task>` `/cc-later:list` `/cc-later:flush`

---

## Development

```bash
git clone https://github.com/vaddisrinivas/cc-manager
cd cc-manager
pip install -e ".[dev]"
pytest tests/ -q          # 148 tests
```

```
cc-manager/
├── cc_manager/
│   ├── cli.py            # Typer app + command registration
│   ├── config.py         # Pydantic settings + all constants
│   ├── context.py        # Paths, loaders, shared helpers, singleton
│   ├── store.py          # Append-only JSONL event log
│   ├── settings.py       # settings.json lock/read/write/backup
│   ├── app.py            # Textual TUI app
│   ├── dashboard_data.py # Pure data layer for TUI
│   ├── commands/         # One file per command
│   ├── handlers/         # Hook event handlers
│   └── widgets/          # Textual widget components
├── registry/
│   └── tools.json        # 35-tool curated catalog
├── scripts/
│   ├── integration_test.sh
│   └── fake_claude.sh
└── tests/                # 148 tests
```

**Dependencies:** typer, rich, textual, pydantic, tomli-w

---

## License

MIT
