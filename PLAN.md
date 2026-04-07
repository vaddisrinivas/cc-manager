# cc-manager Implementation Plan (v0.1 through v0.7)

## Context

cc-manager is a CLI tool that manages the Claude Code ecosystem — installs/removes tools from a curated registry, collects session data via hooks, provides diagnostics, and surfaces insights. It is **not** a runtime plugin; it configures Claude Code and passively observes sessions.

**Distribution:** `uv tool install cc-manager` / `pipx install cc-manager` (Python-only)
**Language:** Python 3.11+
**Dashboard (v0.7):** Small folder served locally, Chart.js via CDN

---

## Dependencies

### Runtime (3 total)

```toml
dependencies = [
    "typer>=0.14.0",      # CLI framework — decorators replace argparse boilerplate
    "rich>=13.0.0",        # Tables, panels, progress, colors, JSON output, Live display
    "tomli-w>=1.0.0",      # TOML writing (tomllib in stdlib is read-only)
]
```

### Dev

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.0.0",
]
```

### Stdlib usage (no deps needed)

| Need | Stdlib module | Notes |
|---|---|---|
| TOML reading | `tomllib` | Python 3.11+ |
| File locking | `fcntl` | Unix only, fine for Claude Code (macOS/Linux) |
| Subprocess | `subprocess` | timeout + capture_output built-in |
| HTTP (v0.5) | `urllib.request` | Registry updates only |
| Analytics | `json` + `collections.Counter` | JSONL aggregation |
| Duration parsing | `re` + `datetime.timedelta` | 10-line parser for `7d`, `30d`, `24h` |
| Version compare | `packaging.version` | Ships with pip/uv toolchain |
| Config templates | f-strings | Static config, no template engine needed |
| JSON diff | 15-line recursive function | Simpler than importing deepdiff |

---

## File Tree (final state at v0.7)

```
cc-manager/
├── pyproject.toml
├── LICENSE
├── README.md
├── cc_manager/
│   ├── __init__.py                  # __version__ only
│   ├── cli.py                       # Typer app + command registration (~20 lines)
│   ├── context.py                   # Paths, loaders, shared context (~100 lines)
│   ├── store.py                     # Event log append/read/query (~80 lines)
│   ├── settings.py                  # settings.json lock/read/write/backup (~60 lines)
│   ├── hook.py                      # Installed to ~/.cc-manager/hook.py (~50 lines)
│   ├── commands/
│   │   ├── __init__.py              # discover_commands() (~15 lines)
│   │   ├── init.py                  # ~60 lines
│   │   ├── install.py               # ~60 lines
│   │   ├── uninstall.py             # ~40 lines
│   │   ├── list_cmd.py              # ~30 lines (list is reserved)
│   │   ├── search.py                # ~25 lines
│   │   ├── info.py                  # ~30 lines
│   │   ├── status.py                # ~40 lines
│   │   ├── doctor.py                # ~50 lines
│   │   ├── audit.py                 # ~40 lines
│   │   ├── diff.py                  # ~35 lines
│   │   ├── why.py                   # ~20 lines
│   │   ├── analyze.py               # ~70 lines
│   │   ├── recommend.py             # ~45 lines
│   │   ├── clean.py                 # ~35 lines
│   │   ├── backup.py                # ~35 lines (backup + restore)
│   │   ├── update.py                # ~35 lines (update + outdated)
│   │   ├── pin.py                   # ~20 lines (pin + unpin)
│   │   ├── export_import.py         # ~35 lines
│   │   ├── config.py                # ~30 lines
│   │   ├── logs.py                  # ~20 lines
│   │   ├── migrate.py               # ~25 lines
│   │   ├── reset.py                 # ~25 lines
│   │   ├── dashboard.py             # v0.7: ~30 lines (generate + serve)
│   │   └── serve.py                 # v0.6: ~40 lines (JSON API)
│   ├── handlers/                    # Hook event handlers
│   │   ├── __init__.py              # handler registry (~15 lines)
│   │   ├── session_start.py         # ~25 lines
│   │   ├── session_end.py           # ~30 lines
│   │   ├── stop.py                  # ~20 lines
│   │   ├── post_tool_use.py         # v0.3: ~25 lines
│   │   └── pre_compact.py           # v0.3: ~20 lines
│   └── dashboard/                   # v0.7: static files
│       ├── index.html
│       ├── style.css
│       └── app.js
├── registry/
│   └── tools.json                   # Bundled tool catalog
└── tests/
    ├── test_context.py
    ├── test_store.py
    ├── test_settings.py
    └── test_commands/
        ├── test_install.py
        ├── test_doctor.py
        └── ...
```

**Estimated total:** ~1000 lines Python + ~300 lines HTML/JS/CSS + registry JSON

---

## Command Contract

Each command is a Typer sub-app. `cli.py` composes them:

```python
# cli.py (~20 lines)
import typer
from cc_manager.commands import install, uninstall, doctor, status, ...

app = typer.Typer(help="Claude Code ecosystem manager")
app.command()(install.run)
app.command()(uninstall.run)
app.command()(doctor.run)
# ...

# Each command file (~15-40 lines):
# commands/doctor.py
import typer
from rich.console import Console
from cc_manager.context import get_ctx

console = Console()

def run(
    json: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Health check — validate config, tools, hooks."""
    ctx = get_ctx()
    results = []
    for tool, meta in ctx.installed["tools"].items():
        code, out = ctx.run_cmd(meta["detect"])
        ok = code == 0
        results.append({"tool": tool, "status": "ok" if ok else "fail", "output": out})

    if json:
        console.print_json(data=results)
        return

    for r in results:
        icon = "[green]✓[/green]" if r["status"] == "ok" else "[red]✗[/red]"
        console.print(f"  {icon}  {r['tool']}")
```

Typer handles: arg parsing, help text, type validation, shell completions. Rich handles: all output formatting.

---

## Handler Contract

Every hook handler module exports:

```python
EVENT = "SessionStart"              # which hook event
TIMEOUT_MS = 5000                   # max runtime

def handle(payload: dict, ctx) -> dict | None:
    """
    payload: JSON from stdin (session_id, cwd, etc.)
    ctx: same Context object
    Returns: dict for stdout JSON (additionalContext, etc.) or None
    """
```

`hook.py` reads argv[1] for event name, dispatches to matching handlers, wraps in try/except with timeout.

---

## Data Model: Event Log

Single append-only file: `~/.cc-manager/store/events.jsonl`

```jsonl
{"ts":"2026-04-06T10:00:00","event":"install","tool":"rtk","version":"0.25.0","method":"cargo"}
{"ts":"2026-04-06T10:00:05","event":"session_start","session":"uuid","cwd":"/path","model":"opus"}
{"ts":"2026-04-06T10:47:00","event":"session_end","session":"uuid","input_tokens":450000,"output_tokens":120000,"cache_read":340000,"cost_usd":0.84,"duration_min":47,"model":"opus"}
{"ts":"2026-04-06T11:00:00","event":"doctor","results":{"rtk":"ok","context7":"ok"}}
{"ts":"2026-04-06T11:05:00","event":"clean","deleted_sessions":3,"freed_bytes":1240000}
{"ts":"2026-04-06T11:10:00","event":"tool_use","session":"uuid","tool":"Bash","command":"npm test"}
{"ts":"2026-04-06T11:15:00","event":"compact","session":"uuid","trigger":"auto","tokens_at_compact":890000}
```

Every cc-manager action logs here. Every hook handler logs here. CLI commands query here.

---

## v0.1 — Foundation + Core Commands

**Goal:** cc-manager is installable, can install/remove tools, shows status, runs doctor.

### Files to write:

1. **pyproject.toml**
   - `[project]` with name, version, python_requires=">=3.11", no dependencies
   - `[project.scripts]` cc-manager = "cc_manager.cli:main", ccm = "cc_manager.cli:main"
   - `[build-system]` hatchling or setuptools

2. **cc_manager/__init__.py**
   ```python
   __version__ = "0.1.0"
   ```

3. **cc_manager/cli.py** (~20 lines)
   - Create Typer app, register each command module
   - `--version` callback
   - Entry point: `app()` — Typer handles everything else (help, arg parsing, completions)

4. **cc_manager/context.py** (~100 lines)
   - Module-level paths: `CLAUDE_DIR`, `MANAGER_DIR`, `SETTINGS_PATH`, `CONFIG_PATH`, etc.
   - `get_ctx() -> Context` — lazy singleton, loads everything once per invocation
   - `class Context`: holds all paths, loaded configs, store handle
   - `load_settings()` → dict (json.load)
   - `load_config()` → dict (tomllib.loads)
   - `save_config(data)` → write TOML via `tomli_w.dumps()`
   - `load_installed()` / `save_installed(data)` → json
   - `load_registry()` → list (from bundled registry/tools.json via `importlib.resources`)
   - `run_cmd(cmd: str, timeout=30) -> tuple[int, str]` → subprocess.run wrapper
   - `parse_duration(spec: str) -> timedelta` — parse `7d`, `30d`, `24h` (~10 lines)

5. **cc_manager/store.py** (~80 lines)
   - `append(event: str, **data)` → write one JSONL line with timestamp
   - `query(event=None, since=None, tool=None, session=None, limit=100) -> list[dict]` → filter + return
   - `latest(event: str) -> dict | None` → last matching event
   - `sessions(since=None) -> list[dict]` → all session_end events, sorted
   - `tail(n=20) -> list[dict]` → last N events

6. **cc_manager/settings.py** (~60 lines)
   - `LOCK_PATH = MANAGER_DIR / ".settings.lock"`
   - `read() -> dict` — json.load with fcntl.flock
   - `write(data: dict, backup=True)` — backup first, then json.dump with indent=2
   - `backup_create() -> Path` — copy to ~/.cc-manager/backups/settings.json.<timestamp>
   - `backup_list() -> list[Path]`
   - `backup_restore(timestamp: str)`
   - `merge_hooks(hooks: dict)` — add cc-manager hook entries without touching others
   - `remove_hooks()` — remove entries where command contains "cc-manager"
   - `merge_mcp(name: str, config: dict)` — add MCP server
   - `remove_mcp(name: str)` — remove MCP server

7. **cc_manager/commands/__init__.py** — empty (Typer doesn't need discovery, cli.py imports directly)

8. **cc_manager/commands/init.py** (~60 lines)
   - Create `~/.cc-manager/` directory structure (store/, backups/)
   - Write default `config.toml` with schema_version=1
   - Backup current settings.json
   - Register hooks in settings.json (Stop, SessionStart, SessionEnd)
   - Install `hook.py` to `~/.cc-manager/hook.py`
   - Prompt for recommended tools (iterate registry where tier=recommended)
   - Call install logic for each accepted tool
   - `--yes` flag: non-interactive, install all recommended
   - `--minimal` flag: no tools, just hooks + config
   - `--dry-run` flag: print what would happen
   - Log `init` event

9. **cc_manager/commands/install.py** (~60 lines)
   - Look up tool in registry by name
   - Check if already installed (installed.json)
   - Check conflicts_with field
   - Based on install.type:
     - `cargo`: `run_cmd("cargo install <pkg>")`
     - `npm`: `run_cmd("npm i -g <pkg>")`
     - `go`: `run_cmd("go install <pkg>")`
     - `pip`: `run_cmd("pip install <pkg>")`
     - `brew`: `run_cmd("brew install <pkg>")`
     - `mcp`: call `settings.merge_mcp(name, mcp_config)`
     - `plugin`: `run_cmd("claude plugin install <id>")`
     - `manual`: print instructions
   - Record in installed.json with version, method, timestamp
   - `--dry-run` support
   - Log `install` event

10. **cc_manager/commands/uninstall.py** (~40 lines)
    - Look up in installed.json
    - If integration=mcp: `settings.remove_mcp(name)`
    - Print uninstall hint (e.g., "run: cargo uninstall rtk") — never auto-uninstall binaries
    - Remove from installed.json
    - Log `uninstall` event

11. **cc_manager/commands/list_cmd.py** (~30 lines)
    - `NAME = "list"`
    - Load registry, filter by `--installed`/`--available`/`--category`/`--tier`
    - Tabulate: name, version (if installed), tier, category, description

12. **cc_manager/commands/search.py** (~25 lines)
    - Fuzzy match query against name + description + category
    - Score by match quality, print top results
    - Simple: `query.lower() in (name + description + category).lower()`

13. **cc_manager/commands/info.py** (~30 lines)
    - Print full registry entry: name, description, category, tier, repo, install method
    - If installed: version, install date, what it wrote to settings.json
    - If not installed: install command preview

14. **cc_manager/commands/status.py** (~40 lines)
    - Show cc-manager version
    - List installed tools with versions (run detect commands)
    - Show hook registration status (how many cc-manager hooks in settings.json)
    - Show last session summary (from store)
    - Show config location

15. **cc_manager/commands/doctor.py** (~50 lines)
    - For each installed tool: run detect command, check version against min_version
    - Check settings.json: are cc-manager hooks registered? Any orphaned MCP entries?
    - Check config.toml: valid TOML, schema_version matches
    - Check store: is events.jsonl writable?
    - Check Python version >= 3.11
    - Print [OK] / [WARN] / [FAIL] for each check
    - Log `doctor` event with results

16. **cc_manager/commands/backup.py** (~35 lines)
    - `backup create`: calls settings.backup_create()
    - `backup list`: calls settings.backup_list(), prints with sizes and dates
    - `backup restore <timestamp>`: creates a backup of current first, then restores

17. **cc_manager/commands/config.py** (~30 lines)
    - `config get <key>`: dot-notation lookup in config dict
    - `config set <key> <value>`: update + save
    - `config edit`: open in $EDITOR
    - `config reset`: write defaults (backup first)

18. **cc_manager/hook.py** (~50 lines)
    - Entry point: `python3 ~/.cc-manager/hook.py <EventName>`
    - Read JSON from stdin
    - Load handler modules from `handlers/`
    - For each handler matching this event:
      - Run with timeout (threading.Timer + subprocess or signal.alarm)
      - Catch exceptions, log failures
      - Collect output dicts
    - Merge outputs, write to stdout
    - Always exit 0 (isolation — one handler crash doesn't block Claude)

19. **cc_manager/handlers/session_start.py** (~25 lines)
    - Quick health check: for each installed tool, run detect command
    - If any missing: return `{"additionalContext": "cc-manager: rtk not found in PATH"}`
    - Log `session_start` event

20. **cc_manager/handlers/session_end.py** (~30 lines)
    - Read session transcript JSONL (path from payload.transcript_path)
    - Sum usage.input_tokens, output_tokens, cache_read_tokens across all messages
    - Compute cost from config pricing table
    - Log `session_end` event with totals

21. **cc_manager/handlers/stop.py** (~20 lines)
    - Log `stop` event (marks active session as ending)
    - Lightweight — SessionEnd does the heavy lifting

22. **registry/tools.json**
    - Curated from Appendix B of SPEC.md
    - ~50 tools for v0.1 (all recommended + popular tier)
    - Schema version 1

### v0.1 Deliverables:
- `uv tool install cc-manager` works
- `ccm --version`, `ccm init`, `ccm install rtk`, `ccm uninstall rtk`
- `ccm list`, `ccm search memory`, `ccm info rtk`
- `ccm status`, `ccm doctor`
- `ccm backup create/list/restore`
- `ccm config get/set/edit`
- Hooks register on init, collect session data passively

---

## v0.2 — Maintenance Commands

**Goal:** Keep installed tools up to date, understand what's in your config.

### Files to add:

1. **cc_manager/commands/update.py** (~35 lines)
   - `update`: for each installed tool, run detect command, compare to registry min_version
   - `update <tool>`: update specific tool (re-run install command)
   - `outdated` (alias): just show what's outdated, don't update
   - Skip pinned tools
   - `--dry-run` support

2. **cc_manager/commands/pin.py** (~20 lines)
   - `pin <tool>`: set `pinned: true` in installed.json
   - `unpin <tool>`: remove pinned flag
   - `pin list`: show all pinned tools

3. **cc_manager/commands/diff.py** (~35 lines)
   - Load latest backup + current settings.json
   - JSON diff: show added/removed/changed keys
   - Color output: green for additions, red for removals

4. **cc_manager/commands/why.py** (~20 lines)
   - `why context7`: search installed.json + events.jsonl for which install added it
   - `why mcpServers.context7`: trace a specific settings.json key to its origin
   - Print: "Added by `ccm install context7` on 2026-04-06"

5. **cc_manager/commands/audit.py** (~40 lines)
   - Parse settings.json completely
   - Categorize every entry:
     - hooks: "cc-manager" (contains ~/.cc-manager/hook.py), "rtk" (contains rtk), "user" (everything else)
     - mcpServers: "cc-manager" (in installed.json), "user" (not)
     - enabledPlugins: "cc-manager" (in installed.json), "user" (not)
   - Print ownership table

6. **cc_manager/commands/clean.py** (~35 lines)
   - `--sessions`: find JSONL files in ~/.claude/projects/ older than N days (configurable), delete
   - `--backups`: keep only last N backups (configurable), delete rest
   - `--dry-run`: show what would be deleted with sizes
   - `--all`: both
   - Log `clean` event with counts

7. **cc_manager/commands/logs.py** (~20 lines)
   - `logs`: tail last 20 events from events.jsonl
   - `logs --event=install`: filter by event type
   - `logs --tool=rtk`: filter by tool
   - `logs --since=7d`: filter by time
   - `logs -f` / `--follow`: tail -f the file

### v0.2 Deliverables:
- `ccm update`, `ccm outdated`, `ccm pin rtk`, `ccm unpin rtk`
- `ccm diff`, `ccm why context7`, `ccm audit`
- `ccm clean --sessions --dry-run`
- `ccm logs --event=install`

---

## v0.3 — Analytics Engine

**Goal:** Turn passively collected hook data into actionable insights.

### Files to add/modify:

1. **cc_manager/handlers/post_tool_use.py** (~25 lines)
   - Track which tools Claude uses: Bash commands, Edit targets, Read targets
   - Log `tool_use` event with tool name and key input fields
   - Matcher: all tools (no matcher = match everything)

2. **cc_manager/handlers/pre_compact.py** (~20 lines)
   - Log `compact` event with trigger (manual/auto), token count at compact time
   - Tracks context pressure — frequent compactions = large context usage

3. **cc_manager/commands/analyze.py** (~70 lines)
   - `analyze`: default last 7 days
   - `analyze --period=30d`
   - `analyze --session=<uuid>`
   - Reads session_end events from store, computes:
     - Total tokens (input, output, cache read, cache write)
     - Total estimated cost (from config pricing)
     - Sessions per day
     - Average session duration
     - Average tokens per session
     - Compaction frequency
     - Model breakdown (sonnet vs opus %)
     - Top Bash commands (from tool_use events)
   - Output as table or `--json`

4. **cc_manager/commands/recommend.py** (~45 lines)
   - Rules engine based on collected data + installed tools:
     - "No token compression tool installed + avg session >500K tokens → suggest rtk"
     - "High compaction frequency → suggest context compression tools"
     - "Running `npm test` >20 times/week → suggest CI integration"
     - "No MCP servers installed → suggest context7, playwright"
     - "No security tool → suggest trail-of-bits"
     - "Using opus >50% → suggest model routing for cost savings"
   - Each rule: condition function + recommendation text + tool name
   - Print: "Based on your usage: [recommendation]. Install with: ccm install <tool>"

5. **Update hook registration** in init.py:
   - Add PostToolUse hook (no matcher — catches all tool uses)
   - Add PreCompact hook

### v0.3 Deliverables:
- `ccm analyze` shows token/cost breakdown
- `ccm analyze --period=30d --json`
- `ccm recommend` suggests tools based on actual usage
- PostToolUse and PreCompact hooks collecting data

---

## v0.4 — Portability + Team Features

**Goal:** Share setups, move between machines.

### Files to add:

1. **cc_manager/commands/export_import.py** (~35 lines)
   - `export`: dump to stdout or file:
     ```json
     {
       "schema_version": 1,
       "cc_manager_version": "0.4.0",
       "exported_at": "2026-04-06T12:00:00",
       "config": { ... },
       "tools": [
         {"name": "rtk", "version": "0.25.0", "method": "cargo"},
         {"name": "context7", "method": "mcp"}
       ]
     }
     ```
   - `import <file>`: read export file, run `install` for each tool, write config
   - `import --dry-run`: show what would be installed
   - Useful for: team onboarding ("run `ccm import team.json`"), machine migration

2. **cc_manager/commands/migrate.py** (~25 lines)
   - `migrate --check`: compare current config schema_version to expected
   - `migrate`: run transforms to bring config up to date
   - Transform registry:
     ```python
     MIGRATIONS = {
       1: migrate_v1_to_v2,  # e.g., rename keys, add new sections
       2: migrate_v2_to_v3,
     }
     ```
   - Always backup before migrating

3. **cc_manager/commands/reset.py** (~25 lines)
   - `reset <tool>`: uninstall + reinstall from registry
   - `reset --all`: uninstall everything, re-run init
   - `reset --config`: reset config.toml to defaults (backup first)
   - Confirm before any destructive action

### v0.4 Deliverables:
- `ccm export > my-setup.json`
- `ccm import team-setup.json`
- `ccm migrate --check`, `ccm migrate`
- `ccm reset rtk`, `ccm reset --all`

---

## v0.5 — Community Commands + Registry Updates

**Goal:** Extensible command system, live registry.

### Changes:

1. **Command plugin discovery** — modify `commands/__init__.py`:
   - Scan `~/.cc-manager/commands/` in addition to built-in commands
   - User drops a `.py` file with the standard contract → it becomes a command
   - `ccm commands list`: show all commands with source (built-in vs user)

2. **Registry update** — add to `commands/init.py` or new `commands/registry.py` (~25 lines):
   - `ccm registry update`: fetch latest tools.json from GitHub raw URL
   - Store in `~/.cc-manager/registry/tools.json` (overrides bundled)
   - `ccm registry reset`: delete override, revert to bundled
   - Compare schema_versions before applying

3. **Completions** — add `commands/completions.py` (~20 lines):
   - `ccm completions bash|zsh|fish`: print shell completion script
   - Standard argparse completion generation

### v0.5 Deliverables:
- User-defined commands in ~/.cc-manager/commands/
- `ccm registry update` fetches latest catalog
- Shell completions

---

## v0.6 — Local JSON API

**Goal:** Machine-readable interface for dashboards and integrations.

### Files to add:

1. **cc_manager/commands/serve.py** (~40 lines)
   - `ccm serve [--port=9847]`
   - `http.server` based — stdlib only, no framework
   - Routes (all GET, all return JSON):
     - `/api/status` — same as `ccm status --json`
     - `/api/tools` — installed tools list
     - `/api/sessions?since=7d` — session summaries
     - `/api/analyze?period=7d` — analytics data
     - `/api/events?limit=100` — raw events
     - `/api/doctor` — health check results
     - `/api/recommend` — recommendations
   - Each route calls the corresponding command's logic with `--json` flag
   - CORS headers for local dashboard access
   - Simple routing: parse URL path, dispatch to handler function

### v0.6 Deliverables:
- `ccm serve` runs local API on port 9847
- All analytics/status data available as JSON endpoints
- Foundation for v0.7 dashboard

---

## v0.7 — HTML Dashboard

**Goal:** Visual dashboard served locally, reads from v0.6 API.

### Files to add:

1. **cc_manager/dashboard/index.html** (~80 lines)
   - CDN imports: Chart.js, (optional: Pico CSS or similar minimal CSS framework)
   - Layout: header + grid of cards
   - Cards: Token Usage (line chart), Cost (bar chart), Tools (table), Sessions (table), Health (status indicators), Recommendations (list)
   - Fetches from `http://localhost:9847/api/*` on load
   - Auto-refresh every 60s

2. **cc_manager/dashboard/style.css** (~100 lines)
   - Dark theme (matches terminal aesthetic)
   - CSS grid layout
   - Card styling
   - Responsive (works on mobile for checking remotely)

3. **cc_manager/dashboard/app.js** (~120 lines)
   - `fetchAll()` — parallel fetch from all API endpoints
   - `renderTokenChart(data)` — Chart.js line chart: tokens per day
   - `renderCostChart(data)` — Chart.js bar chart: cost per day, stacked by model
   - `renderToolsTable(data)` — installed tools with status indicators
   - `renderSessionsTable(data)` — recent sessions with duration, tokens, cost
   - `renderHealth(data)` — green/yellow/red dots for each doctor check
   - `renderRecommendations(data)` — cards with install buttons (copy command to clipboard)

4. **cc_manager/commands/dashboard.py** (~30 lines)
   - `ccm dashboard`: start serve in background, open browser to localhost:9847
   - `ccm dashboard --no-open`: just print URL
   - Serves static files from `cc_manager/dashboard/` directory
   - API endpoints from v0.6 serve.py
   - Single server handles both static files and API routes

5. **Update serve.py** (~10 lines added):
   - Add static file serving for `/` and `/dashboard/*` paths
   - Serve index.html, style.css, app.js from package's dashboard/ directory

### Dashboard Layout:

```
┌──────────────────────────────────────────────────────┐
│  cc-manager dashboard          Last updated: 10s ago │
├──────────────────────┬───────────────────────────────┤
│  Token Usage (7d)    │  Cost Breakdown (7d)          │
│  [line chart]        │  [stacked bar chart]          │
│                      │                               │
├──────────────────────┼───────────────────────────────┤
│  Installed Tools     │  Health                       │
│  ┌─────┬────┬────┐  │  ● settings.json  OK          │
│  │ rtk │0.25│ ok │  │  ● hooks           OK          │
│  │ ctx7│ -- │ ok │  │  ● rtk             OK          │
│  │ ...                │  ● context7        WARN       │
├──────────────────────┼───────────────────────────────┤
│  Recent Sessions     │  Recommendations              │
│  [table: date, dur,  │  □ Install rtk for 60% token  │
│   tokens, cost,      │    savings. `ccm install rtk`  │
│   model, compacts]   │  □ Add security scanning...    │
└──────────────────────┴───────────────────────────────┘
```

### v0.7 Deliverables:
- `ccm dashboard` opens browser with full visual dashboard
- Token/cost charts via Chart.js
- Live health status
- Recommendations with copy-to-clipboard install commands

---

## Version Summary

| Version | Commands Added | Python LOC | Cumulative |
|---------|---------------|------------|------------|
| v0.1 | init, install, uninstall, list, search, info, status, doctor, backup, config + hooks | ~550 | ~550 |
| v0.2 | update, pin, diff, why, audit, clean, logs | ~150 | ~700 |
| v0.3 | analyze, recommend + 2 new handlers | ~120 | ~820 |
| v0.4 | export/import, migrate, reset | ~65 | ~885 |
| v0.5 | community commands, registry update, completions | ~45 | ~930 |
| v0.6 | serve (JSON API) | ~40 | ~970 |
| v0.7 | dashboard command + HTML/CSS/JS | ~30 + ~300 | ~1000 + ~300 |

**Python total: ~1000 lines. Dashboard: ~300 lines HTML/CSS/JS.** Typer + Rich save ~350 LOC vs stdlib-only approach.

---

## Development Method: Test-First, 100% Coverage

**Every version starts by writing tests. Code is written to make tests pass. No exceptions.**

- Framework: `unittest` (stdlib). No pytest, no deps.
- Coverage: `python -m coverage run -m unittest discover && python -m coverage report --fail-under=100`
- Mocking: `unittest.mock` — patch `subprocess.run`, file I/O, stdin/stdout
- Fixtures: `tempfile.TemporaryDirectory` for fake `~/.claude/` and `~/.cc-manager/`
- Test naming: `test_<command>_<scenario>_<expected>` e.g. `test_install_missing_tool_exits_1`
- Negative tests: **every command gets more negative tests than positive**. Bad input, missing files, corrupt JSON, permission denied, subprocess failures, timeouts, concurrent access.

### Test Infrastructure (written before any command)

```
tests/
├── __init__.py
├── fixtures.py                  # Shared test helpers
├── test_context.py
├── test_store.py
├── test_settings.py
├── test_cli.py
├── test_hook.py
├── test_commands/
│   ├── __init__.py
│   ├── test_init.py
│   ├── test_install.py
│   ├── test_uninstall.py
│   ├── ... (one per command)
│   └── test_dashboard.py
└── test_handlers/
    ├── __init__.py
    ├── test_session_start.py
    ├── test_session_end.py
    └── test_stop.py
```

**tests/conftest.py** — shared pytest fixtures:

```python
import pytest, json, tempfile
from pathlib import Path
from unittest.mock import patch
from typer.testing import CliRunner
from cc_manager.cli import app

@pytest.fixture
def env(tmp_path):
    """Isolated fake ~/.claude/ and ~/.cc-manager/ for each test."""
    claude_dir = tmp_path / ".claude"
    manager_dir = tmp_path / ".cc-manager"
    claude_dir.mkdir()
    manager_dir.mkdir()
    (manager_dir / "store").mkdir()
    (manager_dir / "backups").mkdir()

    # Write minimal valid files
    (claude_dir / "settings.json").write_text("{}")
    (manager_dir / "config.toml").write_text('schema_version = 1\n')
    (manager_dir / "installed.json").write_text('{"schema_version": 1, "tools": {}}')

    with patch("cc_manager.context.CLAUDE_DIR", claude_dir), \
         patch("cc_manager.context.MANAGER_DIR", manager_dir):
        yield type("Env", (), {
            "claude_dir": claude_dir,
            "manager_dir": manager_dir,
            "settings": claude_dir / "settings.json",
            "config": manager_dir / "config.toml",
            "installed": manager_dir / "installed.json",
            "events": manager_dir / "store" / "events.jsonl",
            "write_settings": lambda data: (claude_dir / "settings.json").write_text(json.dumps(data)),
            "read_settings": lambda: json.loads((claude_dir / "settings.json").read_text()),
            "write_installed": lambda data: (manager_dir / "installed.json").write_text(json.dumps(data)),
            "read_installed": lambda: json.loads((manager_dir / "installed.json").read_text()),
            "write_events": lambda events: (manager_dir / "store" / "events.jsonl").write_text(
                "\n".join(json.dumps(e) for e in events) + "\n"
            ),
            "read_events": lambda: [json.loads(l) for l in (manager_dir / "store" / "events.jsonl").read_text().splitlines() if l.strip()],
        })()

@pytest.fixture
def runner():
    """Typer CLI test runner."""
    return CliRunner()

@pytest.fixture
def invoke(runner):
    """Shorthand: invoke("install rtk") → Result."""
    def _invoke(cmd_str):
        return runner.invoke(app, cmd_str.split())
    return _invoke
```

**Test style with pytest:**
```python
# tests/test_commands/test_doctor.py
def test_doctor_all_healthy(env, invoke, mocker):
    mocker.patch("cc_manager.context.run_cmd", return_value=(0, "rtk 0.25.0"))
    env.write_installed({"schema_version": 1, "tools": {"rtk": {"detect": "rtk --version"}}})
    result = invoke("doctor")
    assert result.exit_code == 0
    assert "✓" in result.output

def test_doctor_tool_binary_missing(env, invoke, mocker):
    mocker.patch("cc_manager.context.run_cmd", return_value=(1, ""))
    env.write_installed({"schema_version": 1, "tools": {"rtk": {"detect": "rtk --version"}}})
    result = invoke("doctor")
    assert "✗" in result.output
```

---

### v0.1 Tests (written first, before any implementation)

#### test_context.py — 15 tests

```
Positive:
- test_load_settings_valid_json
- test_load_config_valid_toml
- test_load_installed_valid_json
- test_load_registry_valid_json
- test_run_cmd_success
- test_run_cmd_captures_stdout

Negative:
- test_load_settings_file_missing_returns_empty_dict
- test_load_settings_corrupt_json_raises
- test_load_settings_not_a_dict_raises
- test_load_config_file_missing_returns_defaults
- test_load_config_invalid_toml_raises
- test_load_installed_file_missing_returns_empty
- test_load_installed_corrupt_json_raises
- test_load_registry_file_missing_raises_fatal
- test_run_cmd_timeout_returns_error
- test_run_cmd_nonexistent_binary_returns_error
```

#### test_store.py — 18 tests

```
Positive:
- test_append_creates_file_if_missing
- test_append_writes_valid_jsonl
- test_append_adds_timestamp_automatically
- test_query_returns_all_when_no_filter
- test_query_filters_by_event
- test_query_filters_by_since
- test_query_filters_by_tool
- test_query_filters_combined
- test_latest_returns_most_recent
- test_sessions_returns_session_end_events
- test_tail_returns_last_n

Negative:
- test_query_empty_store_returns_empty_list
- test_latest_empty_store_returns_none
- test_query_with_corrupt_line_skips_it
- test_append_to_readonly_dir_raises
- test_query_nonexistent_file_returns_empty
- test_tail_n_larger_than_file_returns_all
- test_append_concurrent_writes_no_corruption (write from 2 threads)
```

#### test_settings.py — 22 tests

```
Positive:
- test_read_valid_settings
- test_write_creates_backup_by_default
- test_write_skips_backup_when_disabled
- test_write_preserves_indent_and_newline
- test_backup_create_returns_path_with_timestamp
- test_backup_list_returns_sorted_by_date
- test_backup_restore_swaps_files
- test_backup_restore_creates_safety_backup_first
- test_merge_hooks_adds_without_overwriting_existing
- test_merge_hooks_idempotent_on_second_run
- test_remove_hooks_only_removes_cc_manager_entries
- test_merge_mcp_adds_server
- test_remove_mcp_removes_server

Negative:
- test_read_missing_file_returns_empty_dict
- test_read_corrupt_json_raises
- test_read_not_a_dict_raises
- test_write_to_readonly_raises
- test_backup_restore_nonexistent_timestamp_raises
- test_merge_hooks_when_settings_has_no_hooks_key
- test_remove_hooks_when_no_cc_manager_hooks_exist_is_noop
- test_remove_mcp_nonexistent_server_is_noop
- test_merge_mcp_when_server_already_exists_warns
- test_lock_timeout_raises (simulate held lock)
- test_concurrent_read_write_no_corruption
```

#### test_cli.py — 10 tests

```
Positive:
- test_version_flag_prints_version
- test_help_lists_all_commands
- test_each_command_has_help_text

Negative:
- test_unknown_command_exits_2
- test_no_subcommand_prints_help_exits_0
- test_command_with_missing_required_arg_exits_2
- test_command_with_invalid_flag_exits_2
- test_command_that_raises_prints_error_exits_1
- test_piped_output_no_ansi_codes (stdout is not tty)
- test_json_flag_produces_valid_json (spot check 3 commands)
```

#### test_commands/test_init.py — 20 tests

```
Positive:
- test_init_creates_manager_dir_structure
- test_init_creates_default_config_toml
- test_init_backs_up_existing_settings
- test_init_registers_hooks_in_settings_json
- test_init_installs_hook_py_to_manager_dir
- test_init_idempotent_second_run_no_duplicates
- test_init_yes_flag_skips_prompts
- test_init_minimal_flag_skips_tools
- test_init_dry_run_creates_nothing
- test_init_logs_init_event

Negative:
- test_init_when_manager_dir_exists_merges_not_overwrites
- test_init_when_settings_json_missing_creates_it
- test_init_when_settings_json_corrupt_fails_gracefully
- test_init_when_claude_dir_missing_fails_with_message
- test_init_when_hook_py_already_exists_overwrites
- test_init_when_hooks_key_missing_from_settings_creates_it
- test_init_when_existing_cc_manager_hooks_replaces_them
- test_init_preserves_non_cc_manager_hooks (rtk, user hooks)
- test_init_preserves_non_cc_manager_mcp_servers
- test_init_when_disk_full_fails_after_backup (mock write failure)
```

#### test_commands/test_install.py — 22 tests

```
Positive:
- test_install_cargo_tool_runs_cargo_install
- test_install_npm_tool_runs_npm_i_g
- test_install_go_tool_runs_go_install
- test_install_pip_tool_runs_pip_install
- test_install_mcp_tool_merges_settings_json
- test_install_plugin_runs_claude_plugin_install
- test_install_records_in_installed_json
- test_install_logs_install_event
- test_install_dry_run_changes_nothing

Negative:
- test_install_unknown_tool_exits_1
- test_install_already_installed_warns_exits_0
- test_install_conflicting_tool_warns_and_prompts
- test_install_cargo_not_in_path_falls_back_to_next_method
- test_install_all_methods_unavailable_exits_1
- test_install_subprocess_fails_exits_1_no_partial_state
- test_install_subprocess_fails_does_not_record_in_installed
- test_install_mcp_settings_write_fails_rolls_back
- test_install_empty_tool_name_exits_2
- test_install_tool_name_with_special_chars_rejected
- test_install_when_installed_json_corrupt_fails_gracefully
- test_install_when_registry_missing_tool_exits_1
- test_install_timeout_on_subprocess_exits_1
```

#### test_commands/test_uninstall.py — 12 tests

```
Positive:
- test_uninstall_removes_from_installed_json
- test_uninstall_mcp_tool_removes_from_settings
- test_uninstall_prints_removal_hint
- test_uninstall_logs_uninstall_event

Negative:
- test_uninstall_not_installed_tool_exits_1
- test_uninstall_unknown_tool_exits_1
- test_uninstall_mcp_removal_fails_still_removes_from_installed
- test_uninstall_empty_name_exits_2
- test_uninstall_when_installed_json_missing_exits_1
- test_uninstall_when_settings_json_locked_retries
- test_uninstall_does_not_run_binary_uninstaller
- test_uninstall_preserves_other_mcp_servers
```

#### test_commands/test_list.py — 10 tests

```
Positive:
- test_list_all_shows_everything
- test_list_installed_shows_only_installed
- test_list_available_shows_only_not_installed
- test_list_category_filters_correctly
- test_list_tier_filters_correctly
- test_list_json_output_valid

Negative:
- test_list_unknown_category_exits_1
- test_list_empty_registry_shows_message
- test_list_when_installed_json_missing_shows_all_as_available
- test_list_with_corrupt_registry_exits_1
```

#### test_commands/test_search.py — 8 tests

```
Positive:
- test_search_by_name_finds_exact
- test_search_by_description_keyword
- test_search_by_category
- test_search_case_insensitive
- test_search_json_output

Negative:
- test_search_no_results_prints_message
- test_search_empty_query_exits_2
- test_search_special_chars_no_crash
```

#### test_commands/test_info.py — 8 tests

```
Positive:
- test_info_installed_tool_shows_version_and_date
- test_info_not_installed_shows_install_command
- test_info_mcp_tool_shows_settings_key
- test_info_json_output

Negative:
- test_info_unknown_tool_exits_1
- test_info_empty_name_exits_2
- test_info_when_installed_json_missing_shows_as_not_installed
- test_info_when_detect_command_fails_shows_unknown_version
```

#### test_commands/test_status.py — 10 tests

```
Positive:
- test_status_shows_version
- test_status_shows_installed_tools
- test_status_shows_hook_count
- test_status_shows_last_session
- test_status_json_output

Negative:
- test_status_no_tools_installed_shows_empty
- test_status_no_hooks_registered_shows_warning
- test_status_no_sessions_shows_none
- test_status_when_detect_command_fails_shows_error_for_tool
- test_status_when_events_jsonl_missing_still_works
```

#### test_commands/test_doctor.py — 16 tests

```
Positive:
- test_doctor_all_healthy
- test_doctor_detects_tool_version
- test_doctor_checks_hooks_registered
- test_doctor_checks_config_valid
- test_doctor_checks_store_writable
- test_doctor_logs_doctor_event
- test_doctor_json_output

Negative:
- test_doctor_tool_binary_missing_reports_fail
- test_doctor_tool_version_below_minimum_reports_warn
- test_doctor_hooks_not_registered_reports_fail
- test_doctor_config_invalid_toml_reports_fail
- test_doctor_config_missing_reports_fail
- test_doctor_store_not_writable_reports_fail
- test_doctor_settings_json_missing_reports_fail
- test_doctor_orphaned_mcp_entry_reports_warn
- test_doctor_python_version_too_old_reports_fail (mock sys.version_info)
```

#### test_commands/test_backup.py — 12 tests

```
Positive:
- test_backup_create_copies_settings
- test_backup_create_returns_path
- test_backup_list_shows_all_backups
- test_backup_restore_swaps_files
- test_backup_restore_creates_safety_backup

Negative:
- test_backup_create_when_settings_missing_exits_1
- test_backup_list_when_no_backups_shows_empty
- test_backup_restore_nonexistent_timestamp_exits_1
- test_backup_restore_when_backup_file_corrupt_exits_1
- test_backup_restore_when_settings_locked_retries
- test_backup_create_when_backups_dir_missing_creates_it
- test_backup_create_when_disk_full_exits_1
```

#### test_commands/test_config.py — 12 tests

```
Positive:
- test_config_get_existing_key
- test_config_get_nested_key
- test_config_set_creates_key
- test_config_set_updates_existing
- test_config_reset_writes_defaults
- test_config_reset_creates_backup

Negative:
- test_config_get_nonexistent_key_exits_1
- test_config_set_invalid_value_type_exits_1
- test_config_edit_when_editor_not_set_exits_1
- test_config_when_toml_corrupt_exits_1
- test_config_set_readonly_file_exits_1
- test_config_get_empty_key_exits_2
```

#### test_hook.py — 15 tests

```
Positive:
- test_hook_dispatches_to_matching_handler
- test_hook_reads_json_from_stdin
- test_hook_writes_json_to_stdout
- test_hook_logs_event_to_store
- test_hook_exits_0_always

Negative:
- test_hook_unknown_event_exits_0_no_crash
- test_hook_no_matching_handlers_exits_0
- test_hook_handler_raises_exception_still_exits_0
- test_hook_handler_timeout_kills_and_continues
- test_hook_corrupt_stdin_json_exits_0
- test_hook_empty_stdin_exits_0
- test_hook_no_argv_event_exits_0
- test_hook_handler_returns_invalid_dict_ignored
- test_hook_multiple_handlers_all_run_even_if_first_fails
- test_hook_store_write_failure_still_exits_0
```

#### test_handlers/test_session_start.py — 8 tests

```
Positive:
- test_session_start_logs_event
- test_session_start_returns_warnings_for_missing_tools
- test_session_start_returns_none_when_all_healthy

Negative:
- test_session_start_no_installed_tools_returns_none
- test_session_start_detect_command_timeout_reports_warning
- test_session_start_installed_json_missing_returns_none
- test_session_start_installed_json_corrupt_returns_none
- test_session_start_payload_missing_fields_still_works
```

#### test_handlers/test_session_end.py — 10 tests

```
Positive:
- test_session_end_reads_transcript_sums_tokens
- test_session_end_computes_cost_from_config
- test_session_end_logs_session_end_event_with_totals
- test_session_end_handles_multiple_models_in_session

Negative:
- test_session_end_transcript_path_missing_logs_partial
- test_session_end_transcript_corrupt_jsonl_skips_bad_lines
- test_session_end_transcript_empty_logs_zero_tokens
- test_session_end_no_usage_field_in_messages_logs_zero
- test_session_end_pricing_config_missing_uses_defaults
- test_session_end_transcript_very_large_doesnt_oom (mock 100K lines)
```

#### test_handlers/test_stop.py — 5 tests

```
Positive:
- test_stop_logs_stop_event
- test_stop_returns_none

Negative:
- test_stop_empty_payload_still_logs
- test_stop_store_write_fails_still_returns_none
- test_stop_no_session_id_in_payload_still_logs
```

**v0.1 test count: ~213 tests**

---

### v0.2 Tests

#### test_commands/test_update.py — 12 tests

```
Positive:
- test_outdated_shows_tools_with_newer_versions
- test_outdated_shows_nothing_when_all_current
- test_update_runs_install_command_for_outdated
- test_update_specific_tool
- test_update_skips_pinned_tools
- test_update_dry_run

Negative:
- test_update_tool_not_installed_exits_1
- test_update_detect_fails_shows_unknown_version
- test_update_no_min_version_in_registry_skips
- test_update_subprocess_fails_exits_1
- test_outdated_when_no_tools_installed
- test_update_when_installed_json_corrupt
```

#### test_commands/test_pin.py — 8 tests

```
Positive:
- test_pin_sets_pinned_flag
- test_unpin_removes_pinned_flag
- test_pin_list_shows_pinned_tools

Negative:
- test_pin_not_installed_tool_exits_1
- test_pin_already_pinned_is_noop
- test_unpin_not_pinned_is_noop
- test_unpin_not_installed_exits_1
- test_pin_list_when_nothing_pinned
```

#### test_commands/test_diff.py — 8 tests

```
Positive:
- test_diff_shows_added_keys
- test_diff_shows_removed_keys
- test_diff_shows_changed_values
- test_diff_no_changes_shows_clean

Negative:
- test_diff_no_backups_exits_1
- test_diff_backup_corrupt_exits_1
- test_diff_settings_missing_exits_1
- test_diff_both_empty_shows_clean
```

#### test_commands/test_why.py — 6 tests

```
Positive:
- test_why_tool_shows_install_event
- test_why_settings_key_traces_to_tool
- test_why_json_output

Negative:
- test_why_unknown_tool_exits_1
- test_why_no_install_events_shows_unknown
- test_why_empty_arg_exits_2
```

#### test_commands/test_audit.py — 10 tests

```
Positive:
- test_audit_categorizes_cc_manager_hooks
- test_audit_categorizes_rtk_hooks
- test_audit_categorizes_user_hooks
- test_audit_categorizes_mcp_servers
- test_audit_json_output

Negative:
- test_audit_empty_settings_shows_empty
- test_audit_no_hooks_key_shows_none
- test_audit_settings_missing_exits_1
- test_audit_installed_json_missing_still_works
- test_audit_malformed_hook_entry_shows_unknown
```

#### test_commands/test_clean.py — 12 tests

```
Positive:
- test_clean_sessions_deletes_old_jsonl
- test_clean_sessions_preserves_recent
- test_clean_backups_keeps_last_n
- test_clean_all_does_both
- test_clean_dry_run_deletes_nothing
- test_clean_logs_clean_event

Negative:
- test_clean_no_sessions_dir_is_noop
- test_clean_no_old_sessions_deletes_nothing
- test_clean_no_backups_is_noop
- test_clean_readonly_file_skips_with_warning
- test_clean_sessions_skips_non_jsonl_files
- test_clean_negative_days_exits_2
```

#### test_commands/test_logs.py — 8 tests

```
Positive:
- test_logs_shows_last_20
- test_logs_filter_by_event
- test_logs_filter_by_tool
- test_logs_filter_by_since

Negative:
- test_logs_empty_store_shows_nothing
- test_logs_corrupt_line_skips_it
- test_logs_invalid_since_format_exits_2
- test_logs_follow_flag_accepted (just verify arg parsing)
```

**v0.2 test count: ~64 tests. Running total: ~277**

---

### v0.3 Tests

#### test_handlers/test_post_tool_use.py — 8 tests

```
Positive:
- test_post_tool_use_logs_bash_command
- test_post_tool_use_logs_edit_file_path
- test_post_tool_use_logs_read_file_path

Negative:
- test_post_tool_use_missing_tool_name_skips
- test_post_tool_use_missing_tool_input_logs_minimal
- test_post_tool_use_very_large_input_truncates
- test_post_tool_use_unknown_tool_name_still_logs
- test_post_tool_use_store_failure_returns_none
```

#### test_handlers/test_pre_compact.py — 6 tests

```
Positive:
- test_pre_compact_logs_compact_event
- test_pre_compact_records_trigger_type

Negative:
- test_pre_compact_missing_trigger_defaults_to_unknown
- test_pre_compact_empty_payload_still_logs
- test_pre_compact_store_failure_returns_none
- test_pre_compact_invalid_trigger_value_logs_raw
```

#### test_commands/test_analyze.py — 16 tests

```
Positive:
- test_analyze_default_7_days
- test_analyze_custom_period_30d
- test_analyze_specific_session
- test_analyze_computes_total_tokens
- test_analyze_computes_cost
- test_analyze_computes_sessions_per_day
- test_analyze_computes_avg_duration
- test_analyze_computes_model_breakdown
- test_analyze_computes_top_bash_commands
- test_analyze_json_output

Negative:
- test_analyze_no_sessions_shows_empty
- test_analyze_invalid_period_format_exits_2
- test_analyze_nonexistent_session_uuid_exits_1
- test_analyze_sessions_with_zero_tokens_included
- test_analyze_sessions_with_missing_cost_uses_zero
- test_analyze_corrupt_events_skipped
```

#### test_commands/test_recommend.py — 12 tests

```
Positive:
- test_recommend_suggests_rtk_when_high_tokens
- test_recommend_suggests_context7_when_no_mcp
- test_recommend_suggests_security_when_no_security_tool
- test_recommend_no_suggestions_when_all_covered
- test_recommend_json_output

Negative:
- test_recommend_no_session_data_still_returns_generic_recs
- test_recommend_all_tools_installed_returns_empty
- test_recommend_corrupt_events_skips_bad_data
- test_recommend_empty_registry_returns_empty
- test_recommend_handles_missing_categories_in_registry
- test_recommend_doesnt_recommend_conflicting_tools
- test_recommend_doesnt_recommend_already_installed
```

**v0.3 test count: ~42 tests. Running total: ~319**

---

### v0.4 Tests

#### test_commands/test_export_import.py — 14 tests

```
Positive:
- test_export_produces_valid_json
- test_export_includes_all_installed_tools
- test_export_includes_config
- test_import_installs_all_tools
- test_import_writes_config
- test_import_dry_run_changes_nothing
- test_round_trip_export_then_import

Negative:
- test_import_invalid_json_exits_1
- test_import_missing_schema_version_exits_1
- test_import_incompatible_schema_exits_1
- test_import_file_not_found_exits_1
- test_import_tool_install_fails_continues_others
- test_export_when_no_tools_installed_still_valid
- test_import_empty_tools_list_is_noop
```

#### test_commands/test_migrate.py — 8 tests

```
Positive:
- test_migrate_check_reports_current
- test_migrate_check_reports_outdated
- test_migrate_runs_transforms
- test_migrate_creates_backup_first

Negative:
- test_migrate_already_current_is_noop
- test_migrate_unknown_schema_version_exits_1
- test_migrate_config_missing_exits_1
- test_migrate_transform_fails_rolls_back
```

#### test_commands/test_reset.py — 10 tests

```
Positive:
- test_reset_tool_uninstalls_and_reinstalls
- test_reset_config_writes_defaults
- test_reset_config_creates_backup

Negative:
- test_reset_unknown_tool_exits_1
- test_reset_not_installed_tool_exits_1
- test_reset_all_without_confirm_exits_1
- test_reset_reinstall_fails_reports_error
- test_reset_config_when_readonly_exits_1
- test_reset_all_removes_all_tools
- test_reset_all_preserves_events_log
```

**v0.4 test count: ~32 tests. Running total: ~351**

---

### v0.5 Tests

#### test_commands/test_commands_list.py (community commands) — 8 tests

```
Positive:
- test_discover_finds_user_commands_in_manager_dir
- test_commands_list_shows_source_builtin_vs_user
- test_user_command_loaded_as_typer_command

Negative:
- test_discover_user_commands_dir_missing_is_fine
- test_discover_user_command_without_run_function_skipped
- test_discover_user_command_with_syntax_error_skipped
- test_discover_user_command_name_collision_builtin_wins
- test_discover_user_command_import_error_logged_and_skipped
```

#### test_commands/test_registry.py — 8 tests

```
Positive:
- test_registry_update_writes_new_tools_json
- test_registry_reset_deletes_override

Negative:
- test_registry_update_fetch_fails_exits_1 (mock urllib)
- test_registry_update_invalid_json_exits_1
- test_registry_update_incompatible_schema_exits_1
- test_registry_reset_when_no_override_is_noop
- test_registry_update_preserves_installed_state
- test_registry_update_network_timeout_exits_1
```

#### test_commands/test_completions.py — 4 tests

```
Positive:
- test_completions_bash_outputs_script
- test_completions_zsh_outputs_script

Negative:
- test_completions_unknown_shell_exits_1
- test_completions_no_shell_arg_exits_2
```

**v0.5 test count: ~20 tests. Running total: ~371**

---

### v0.6 Tests

#### test_commands/test_serve.py — 16 tests

```
Positive:
- test_serve_starts_on_default_port
- test_serve_custom_port
- test_api_status_returns_json
- test_api_tools_returns_installed_list
- test_api_sessions_returns_session_data
- test_api_sessions_since_param_filters
- test_api_analyze_returns_analytics
- test_api_events_returns_events
- test_api_events_limit_param
- test_api_doctor_returns_health
- test_api_recommend_returns_suggestions
- test_api_cors_headers_present

Negative:
- test_api_unknown_route_returns_404
- test_api_post_method_returns_405
- test_serve_port_in_use_exits_1
- test_api_invalid_query_param_returns_400
```

**v0.6 test count: ~16 tests. Running total: ~387**

---

### v0.7 Tests

#### test_commands/test_dashboard.py — 10 tests

```
Positive:
- test_dashboard_starts_server
- test_dashboard_serves_index_html
- test_dashboard_serves_style_css
- test_dashboard_serves_app_js
- test_dashboard_no_open_flag_skips_browser

Negative:
- test_dashboard_missing_static_files_exits_1
- test_dashboard_port_in_use_exits_1
- test_dashboard_api_endpoints_still_work
- test_dashboard_static_file_404_for_unknown
- test_dashboard_no_directory_traversal (security: ../../etc/passwd)
```

**v0.7 test count: ~10 tests. Running total: ~397**

---

### Test Summary

| Version | Tests | Focus |
|---------|-------|-------|
| v0.1 | ~213 | Core infra, install/uninstall, hooks, settings |
| v0.2 | ~64 | Maintenance commands, config management |
| v0.3 | ~42 | Analytics, recommendations, new handlers |
| v0.4 | ~32 | Import/export, migration, reset |
| v0.5 | ~20 | Plugin system, registry updates |
| v0.6 | ~16 | HTTP API |
| v0.7 | ~10 | Dashboard serving + security |
| **Total** | **~397** | **100% coverage, negative-test-heavy** |

---

## Build & Release

**pyproject.toml:**
```toml
[project]
name = "cc-manager"
version = "0.1.0"
description = "Claude Code ecosystem manager"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.14.0",
    "rich>=13.0.0",
    "tomli-w>=1.0.0",
]

[project.scripts]
cc-manager = "cc_manager.cli:app"
ccm = "cc_manager.cli:app"

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.0.0",
    "pytest-mock>=3.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=cc_manager --cov-report=term-missing --cov-fail-under=100"

[tool.coverage.run]
omit = ["tests/*"]
```

**CI pipeline:**
1. `uv build` → wheel
2. `uv publish` → PyPI
3. GitHub Actions: test on Python 3.11, 3.12, 3.13 on ubuntu + macos
4. Tag-based releases: push tag → build → publish to PyPI
5. Coverage gate: `--fail-under=100` in CI — PR blocked if coverage drops
