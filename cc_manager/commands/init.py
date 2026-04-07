"""cc-manager init command — 5-step dramatic interactive setup."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

import typer
from rich import box
from rich.panel import Panel
from rich.padding import Padding
from rich.rule import Rule
from rich.table import Table

import cc_manager.context as ctx_mod
import cc_manager.settings as settings_mod
from cc_manager.context import get_ctx, run_cmd
from cc_manager.display import console, header, success, warning, info, dim_info

# Default config toml content
DEFAULT_CONFIG = """\
[manager]
schema_version = 1
backup_on_change = true
log_level = "info"

[later]
enabled = true

[compact]
enabled = true

[resume]
enabled = true

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

[nudge]
enabled = true
stale_minutes = 10
max_retries = 2
"""

HOOK_EVENTS = ["Stop", "SessionStart", "SessionEnd", "PostToolUse", "PreCompact"]

MODULES = [
    ("later", "dispatch deferred tasks at window end"),
    ("compact", "context recovery after compaction"),
    ("resume", "auto-resume limit-hit tasks"),
    ("budget", "global budget enforcement"),
    ("window", "5-hour window lifecycle"),
    ("stats", "token analytics + cost tracking"),
    ("nudge", "stale agent detection"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _show_step(n: int, total: int, title: str) -> None:
    """Print a numbered step header."""
    console.print()
    console.print(Rule(
        f"[bold bright_cyan]Step {n}/{total}:[/bold bright_cyan] [bright_white]{title}[/bright_white]",
        style="cyan",
    ))
    console.print()


def _detect_tool(tool: dict) -> str | None:
    """Return version string if tool is detected, else None."""
    detect_cmd = tool.get("detect_cmd")
    if detect_cmd:
        rc, output = run_cmd(detect_cmd, timeout=5)
        if rc == 0 and output:
            # Return first line as version hint
            return output.splitlines()[0].strip()[:60]
        return None

    # Fallback: check if primary binary exists on PATH
    name = tool.get("name", "")
    if shutil.which(name):
        return f"found in PATH"
    return None


def _build_hook_entry(event_name: str) -> dict:
    return {
        event_name: [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"python3 ~/.cc-manager/hook.py {event_name}",
                    }
                ],
            }
        ]
    }


def _install_skills(claude_dir: Path, dry_run: bool) -> list[str]:
    """Install skill files to ~/.claude/. Returns list of actions taken."""
    actions: list[str] = []
    skills_src = Path(__file__).parent.parent / "skills"

    if dry_run:
        dim_info("[DRY RUN] would install cc-manager skill files to ~/.claude/")
        return actions

    # Write cc-manager.md to ~/.claude/
    ccm_md_src = skills_src / "cc-manager.md"
    ccm_md_dst = claude_dir / "cc-manager.md"
    if ccm_md_src.exists():
        shutil.copy2(ccm_md_src, ccm_md_dst)
        actions.append("~/.claude/cc-manager.md")

    # Append @cc-manager to CLAUDE.md if not already there
    claude_md = claude_dir / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")
        if "@cc-manager" not in content:
            claude_md.write_text(content + "\n@cc-manager\n", encoding="utf-8")
            actions.append("~/.claude/CLAUDE.md (@cc-manager appended)")
    else:
        claude_md.write_text("@cc-manager\n", encoding="utf-8")
        actions.append("~/.claude/CLAUDE.md (created)")

    # Install SKILL.md to ~/.claude/skills/cc-manager/
    skill_src = skills_src / "SKILL.md"
    if skill_src.exists():
        skills_dst = claude_dir / "skills" / "cc-manager"
        skills_dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_src, skills_dst / "SKILL.md")
        actions.append("~/.claude/skills/cc-manager/SKILL.md")

    return actions


def _install_hook_script(manager_dir: Path, dry_run: bool) -> None:
    """Copy hook.py to ~/.cc-manager/hook.py."""
    dest = manager_dir / "hook.py"
    if dry_run:
        dim_info(f"[DRY RUN] would install hook.py to {dest}")
        return

    candidates = [
        Path(__file__).parent.parent / "hook.py",
    ]
    for src in candidates:
        if src.exists():
            shutil.copy2(src, dest)
            return

    # Fall back: write minimal stub
    dest.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, json\n"
        "# cc-manager hook dispatcher\n"
        "# Re-run: ccm init to update this file\n"
        "print('{}')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )


def _prompt_yes(msg: str, default: bool = True) -> bool:
    try:
        return typer.confirm(msg, default=default)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------

def _step1_detect_environment(dry_run: bool) -> dict:
    """Step 1/5: Detecting environment. Returns detection results."""
    _show_step(1, 5, "Detecting environment")

    results = {}

    with console.status("[bright_cyan]Scanning environment...[/bright_cyan]", spinner="dots12"):
        # Claude Code config dir
        results["claude_dir_exists"] = ctx_mod.CLAUDE_DIR.exists()
        results["settings_exists"] = ctx_mod.SETTINGS_PATH.exists()

        # Existing non-cc-manager hooks
        existing_hooks: list[str] = []
        if ctx_mod.SETTINGS_PATH.exists():
            import json
            try:
                data = json.loads(ctx_mod.SETTINGS_PATH.read_text(encoding="utf-8"))
                hooks_data = data.get("hooks", {})
                for event_name, hook_list in hooks_data.items():
                    for entry in (hook_list if isinstance(hook_list, list) else []):
                        for h in entry.get("hooks", []):
                            cmd = h.get("command", "")
                            if ".cc-manager" not in cmd:
                                existing_hooks.append(f"{Path(cmd.split()[0]).name} ({event_name})")
            except Exception:
                pass
        results["existing_hooks"] = existing_hooks

        # Python version
        rc, py_out = run_cmd("python3 --version", timeout=5)
        results["python"] = py_out.strip() if rc == 0 else None

        # Tool binaries
        for bin_name in ("cargo", "go", "npm", "pip"):
            results[bin_name] = shutil.which(bin_name) is not None

    # Display results panel
    def _found(val: bool) -> str:
        return "[bright_green]found[/bright_green]" if val else "[dim]not found[/dim]"

    settings_label = "[bright_green]found[/bright_green]" if results["settings_exists"] else "[yellow]not found[/yellow]"
    hooks_label = (
        f"[bright_white]{', '.join(results['existing_hooks'][:2])}[/bright_white]"
        if results["existing_hooks"]
        else "[dim]none[/dim]"
    )
    python_label = (
        f"[bright_white]{results['python']}[/bright_white]"
        if results["python"]
        else "[dim]not found[/dim]"
    )

    claude_dir_str = str(ctx_mod.CLAUDE_DIR).replace(str(Path.home()), "~")
    settings_str = str(ctx_mod.SETTINGS_PATH).replace(str(Path.home()), "~")

    lines = [
        f"  [bright_cyan]◆[/bright_cyan] Claude Code config    [dim]{claude_dir_str}[/dim]               {_found(results['claude_dir_exists'])}",
        f"  [bright_cyan]◆[/bright_cyan] settings.json         [dim]{settings_str}[/dim]  {settings_label}",
        f"  [bright_cyan]◆[/bright_cyan] Existing hooks         {hooks_label}",
        f"  [bright_cyan]◆[/bright_cyan] Python                 {python_label}",
        f"  [bright_cyan]◆[/bright_cyan] cargo                  {_found(results['cargo'])}",
        f"  [bright_cyan]◆[/bright_cyan] go                     {_found(results['go'])}",
        f"  [bright_cyan]◆[/bright_cyan] npm                    {_found(results['npm'])}",
        f"  [bright_cyan]◆[/bright_cyan] pip                    {_found(results['pip'])}",
    ]

    console.print(
        Panel(
            "\n".join(lines),
            border_style="cyan",
            box=box.SIMPLE_HEAVY,
            padding=(0, 1),
        )
    )

    return results


def _step2_backup(dry_run: bool) -> str | None:
    """Step 2/5: Back up existing settings. Returns backup path or None."""
    _show_step(2, 5, "Backing up current config")

    if not ctx_mod.SETTINGS_PATH.exists():
        dim_info("No settings.json found — skipping backup.")
        return None

    if dry_run:
        dim_info("[DRY RUN] would back up settings.json")
        return None

    console.print(f"  [bright_cyan]◆[/bright_cyan]  Backing up settings.json...")
    bpath = settings_mod.backup_create()
    bpath_str = str(bpath).replace(str(Path.home()), "~")
    console.print(f"  [bright_green]✓[/bright_green]  [dim]{bpath_str}[/dim]")
    return str(bpath)


def _step3_install_tools(dry_run: bool, minimal: bool, yes: bool) -> list[str]:
    """Step 3/5: Install recommended tools. Returns list of installed tool names."""
    _show_step(3, 5, "Installing recommended tools")

    installed_tools: list[str] = []

    if minimal:
        dim_info("--minimal: skipping tool installation.")
        return installed_tools

    ctx = get_ctx()
    recommended = [t for t in ctx.registry if t.get("tier") == "recommended"]

    if not recommended:
        dim_info("No recommended tools found in registry.")
        return installed_tools

    total = len(recommended)

    from cc_manager.commands.install import install_tool, AlreadyInstalledError, ToolNotFoundError, InstallError

    for idx, tool in enumerate(recommended, 1):
        name = tool.get("name", "?")
        desc = tool.get("description", "")
        methods = tool.get("install_methods", [])
        method = methods[0] if methods else {}
        method_type = method.get("type", "unknown")
        method_cmd = method.get("command", "")

        # Build method hint
        if method_type == "mcp":
            method_hint = "[dim]→ adds to mcpServers in settings.json[/dim]"
        elif method_type == "plugin":
            plugin_cmd = method_cmd or f"claude plugin install {name}"
            method_hint = f"[dim]→ {plugin_cmd}[/dim]"
        elif method_type in ("github_action", "manual"):
            method_hint = "[yellow]→ manual setup required[/yellow]"
        else:
            method_hint = f"[dim]→ {method_cmd}[/dim]" if method_cmd else f"[dim]→ {method_type}[/dim]"

        # Detect if already installed
        version = _detect_tool(tool)
        already = name in ctx.installed.get("tools", {})

        prefix = f"  [{idx}/{total}] [bright_white]{name}[/bright_white]"
        dashes = "─" * max(1, 16 - len(name))

        if already or version:
            version_str = version or "installed"
            console.print(f"{prefix} {dashes} [dim]{version_str}[/dim]  [dim]already installed[/dim]  [dim italic][SKIP][/dim italic]")
            continue

        console.print(f"{prefix} {dashes} [dim]{desc[:50]}[/dim]")
        console.print(f"         {method_hint}")

        if dry_run:
            console.print(f"         [dim][DRY RUN] would install[/dim]")
            continue

        # Prompt
        if yes:
            do_install = True
        elif method_type in ("github_action", "manual"):
            instructions = method.get("instructions", "See repository for manual install instructions.")
            console.print(
                Panel(
                    f"[yellow]{instructions}[/yellow]",
                    border_style="yellow",
                    box=box.SIMPLE_HEAVY,
                    padding=(0, 1),
                )
            )
            do_install = _prompt_yes("         Mark as noted?", default=True)
        else:
            do_install = _prompt_yes(f"         Install? ({method_cmd or method_type})", default=True)

        if not do_install:
            console.print("         [dim]Skipped.[/dim]")
            continue

        # Execute install
        try:
            if method_type in ("github_action", "manual"):
                # Just record it
                from cc_manager.commands.install import _record_installed
                _record_installed(name, "manual", ctx)
                console.print(f"         [bright_green]✓[/bright_green] Noted.")
            else:
                with console.status(f"         [bright_cyan]◆ Installing...[/bright_cyan]", spinner="dots12"):
                    install_tool(name, dry_run=False)
                console.print(f"         [bright_green]✓[/bright_green] done")
                installed_tools.append(name)
        except AlreadyInstalledError:
            console.print(f"         [dim]Already installed.[/dim]")
        except (ToolNotFoundError, InstallError, Exception) as e:
            warning(f"Failed to install {name}: {e}")

    return installed_tools


def _step4_enable_modules(dry_run: bool, minimal: bool, yes: bool) -> list[str]:
    """Step 4/5: Enable cc-manager modules. Returns list of enabled module names."""
    _show_step(4, 5, "Enabling cc-manager modules")

    enabled_modules = []

    for mod_name, mod_desc in MODULES:
        if minimal or yes:
            # All on without prompting
            console.print(f"  [bright_green][✓][/bright_green] [bright_white]{mod_name:<10}[/bright_white]  [dim]— {mod_desc}[/dim]")
            enabled_modules.append(mod_name)
        else:
            # Interactive toggle — default all on
            do_enable = _prompt_yes(
                f"  Enable [bright_white]{mod_name}[/bright_white] — {mod_desc}?",
                default=True,
            )
            marker = "[bright_green][✓][/bright_green]" if do_enable else "[dim][ ][/dim]"
            console.print(f"  {marker} [bright_white]{mod_name:<10}[/bright_white]  [dim]— {mod_desc}[/dim]")
            if do_enable:
                enabled_modules.append(mod_name)

    return enabled_modules


def _step5_write_config(
    dry_run: bool,
    manager_dir: Path,
    config_path: Path,
) -> dict:
    """Step 5/5: Write configuration files. Returns summary dict."""
    _show_step(5, 5, "Writing configuration")

    summary = {
        "dirs_created": False,
        "config_written": False,
        "hook_script_installed": False,
        "hooks_merged": 0,
    }

    if dry_run:
        console.print(f"  [dim][DRY RUN] would create[/dim] [bright_white]{str(manager_dir).replace(str(Path.home()), '~')}/{{store,backups,registry,state}}[/bright_white]")
        console.print(f"  [dim][DRY RUN] would write[/dim]  [bright_white]{str(config_path).replace(str(Path.home()), '~')}[/bright_white]")
        console.print(f"  [dim][DRY RUN] would register hooks:[/dim] [bright_cyan]{', '.join(HOOK_EVENTS)}[/bright_cyan]")
        console.print(f"  [dim][DRY RUN] would install[/dim] [bright_white]{str(manager_dir / 'hook.py').replace(str(Path.home()), '~')}[/bright_white]")
        return summary

    # Create directory structure
    for subdir in ("store", "backups", "registry", "state"):
        (manager_dir / subdir).mkdir(parents=True, exist_ok=True)
    dirs_str = str(manager_dir).replace(str(Path.home()), "~")
    console.print(f"  [bright_green]✓[/bright_green]  [bright_white]{dirs_str}/[/bright_white]  [dim](directories created)[/dim]")
    summary["dirs_created"] = True

    # Write default config if not present
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
        cfg_str = str(config_path).replace(str(Path.home()), "~")
        console.print(f"  [bright_green]✓[/bright_green]  [bright_white]{cfg_str}[/bright_white]  [dim](config written)[/dim]")
        summary["config_written"] = True
    else:
        cfg_str = str(config_path).replace(str(Path.home()), "~")
        console.print(f"  [bright_green]✓[/bright_green]  [bright_white]{cfg_str}[/bright_white]  [dim](already exists)[/dim]")
        summary["config_written"] = True

    # Install hook.py
    _install_hook_script(manager_dir, dry_run=False)
    hook_str = str(manager_dir / "hook.py").replace(str(Path.home()), "~")
    console.print(f"  [bright_green]✓[/bright_green]  [bright_white]{hook_str}[/bright_white]  [dim](dispatcher installed)[/dim]")
    summary["hook_script_installed"] = True

    # Register hooks
    hooks: dict = {}
    for event in HOOK_EVENTS:
        hooks.update(_build_hook_entry(event))
    settings_mod.merge_hooks(hooks)
    settings_str = str(ctx_mod.SETTINGS_PATH).replace(str(Path.home()), "~")
    console.print(
        f"  [bright_green]✓[/bright_green]  [bright_white]{settings_str}[/bright_white]  "
        f"[dim](merged: {len(HOOK_EVENTS)} hook entries)[/dim]"
    )
    summary["hooks_merged"] = len(HOOK_EVENTS)

    # Install skill files
    skill_actions = _install_skills(claude_dir=ctx_mod.CLAUDE_DIR, dry_run=False)
    for action in skill_actions:
        console.print(f"  [bright_green]✓[/bright_green]  [bright_white]{action}[/bright_white]  [dim](skills installed)[/dim]")
    summary["skills_installed"] = skill_actions

    return summary


# ---------------------------------------------------------------------------
# Core init function
# ---------------------------------------------------------------------------

def run_init(dry_run: bool = False, minimal: bool = False, yes: bool = False) -> None:
    """Core init logic (called by CLI and tests)."""
    manager_dir = ctx_mod.MANAGER_DIR
    config_path = ctx_mod.CONFIG_PATH

    # Show header
    header("cc-manager init")
    console.print(
        Padding(
            "[dim]Intelligent Claude Code ecosystem controller — interactive setup[/dim]",
            (0, 2),
        )
    )
    console.print()

    if dry_run:
        console.print(
            Panel(
                "[bold yellow]Nothing will be written. Showing full plan.[/bold yellow]",
                title="[bold yellow]⚠ DRY RUN MODE[/bold yellow]",
                border_style="yellow",
                box=box.HEAVY,
                padding=(0, 1),
            )
        )

    # ── Step 1: Detect environment ────────────────────────────────────────────
    _step1_detect_environment(dry_run=dry_run)

    # ── Step 2: Backup ────────────────────────────────────────────────────────
    _step2_backup(dry_run=dry_run)

    # ── Step 3: Install tools ─────────────────────────────────────────────────
    installed_tools = _step3_install_tools(dry_run=dry_run, minimal=minimal, yes=yes)

    # ── Step 4: Enable modules ────────────────────────────────────────────────
    enabled_modules = _step4_enable_modules(dry_run=dry_run, minimal=minimal, yes=yes)

    # ── Step 5: Write config ──────────────────────────────────────────────────
    summary = _step5_write_config(dry_run=dry_run, manager_dir=manager_dir, config_path=config_path)

    if dry_run:
        console.print()
        dim_info("[DRY RUN] No files were written.")
        console.print()
        return

    # Reset ctx so next get_ctx() picks up fresh state
    ctx_mod._ctx = None
    ctx = get_ctx()

    # Log init event
    ctx.store.append("init", minimal=minimal)

    # ── Final summary panel ───────────────────────────────────────────────────
    hooks_list = ", ".join(HOOK_EVENTS[:3]) + f",\n    {', '.join(HOOK_EVENTS[3:])}"
    tools_count = len(installed_tools)
    hooks_count = summary.get("hooks_merged", len(HOOK_EVENTS))
    modules_count = len(enabled_modules)

    summary_lines = [
        f"  [bright_green]✓[/bright_green]  [bright_white]{tools_count} tool{'s' if tools_count != 1 else ''} installed[/bright_white]",
        f"  [bright_green]✓[/bright_green]  [bright_white]{hooks_count} hooks registered[/bright_white] [dim]({hooks_list})[/dim]",
        f"  [bright_green]✓[/bright_green]  [bright_white]{modules_count} module{'s' if modules_count != 1 else ''} enabled[/bright_white]",
    ]

    console.print()
    console.print(
        Panel(
            "\n".join(summary_lines),
            title="[bold bright_cyan]◉ INITIALIZATION COMPLETE[/bold bright_cyan]",
            border_style="bright_cyan",
            box=box.DOUBLE_EDGE,
            padding=(0, 1),
        )
    )
    console.print()
    console.print(
        Padding(
            "[dim]Run[/dim] [bright_cyan]ccm status[/bright_cyan] [dim]to verify.[/dim]",
            (0, 2),
        )
    )
    console.print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

app = typer.Typer()


@app.command("init")
def init_cmd(
    dry_run: bool = typer.Option(False, "--dry-run", help="Print what would happen, write nothing"),
    minimal: bool = typer.Option(False, "--minimal", help="Hooks + config only, no tools"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Non-interactive, install all recommended"),
) -> None:
    """Initialize cc-manager: create dirs, config, register hooks."""
    run_init(dry_run=dry_run, minimal=minimal, yes=yes)
