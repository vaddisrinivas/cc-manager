"""cc-manager init command."""
from __future__ import annotations

import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import typer
from rich import box
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.rule import Rule
from rich.table import Table

import cc_manager.context as ctx_mod
import cc_manager.settings as settings_mod
from cc_manager.config import HOOK_EVENTS, MODULES, cfg
from cc_manager.context import get_ctx, run_cmd
from cc_manager.display import console, dim_info, header, success


# ── Helpers ────────────────────────────────────────────────────────────────────

def _step(n: int, total: int, title: str) -> None:
    console.print()
    console.print(Rule(f"[bold bright_cyan]Step {n}/{total}:[/bold bright_cyan] [bright_white]{title}[/bright_white]", style="cyan"))
    console.print()


def _detect_tool(tool: dict) -> bool:
    detect = tool.get("detect", {})
    cmd = detect.get("command", "")
    if cmd:
        rc, _ = run_cmd(cmd, timeout=5)
        return rc == 0
    return bool(shutil.which(tool.get("name", "")))


def _build_hook_entry(event: str) -> dict:
    return {event: [{"matcher": "", "hooks": [{"type": "command", "command": f"python3 ~/.cc-manager/hook.py {event}"}]}]}


def _install_skills(claude_dir: Path, dry_run: bool) -> list[str]:
    if dry_run:
        return []
    actions: list[str] = []
    src = Path(__file__).parent.parent / "skills"
    ccm_md = src / "cc-manager.md"
    if ccm_md.exists():
        shutil.copy2(ccm_md, claude_dir / "cc-manager.md")
        actions.append("~/.claude/cc-manager.md")
    claude_md = claude_dir / "CLAUDE.md"
    text = claude_md.read_text(encoding="utf-8") if claude_md.exists() else ""
    if "@cc-manager" not in text:
        claude_md.write_text(text + "\n@cc-manager\n", encoding="utf-8")
        actions.append("~/.claude/CLAUDE.md")
    skill_src = src / "SKILL.md"
    if skill_src.exists():
        dst = claude_dir / "skills" / "cc-manager"
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_src, dst / "SKILL.md")
        actions.append("~/.claude/skills/cc-manager/SKILL.md")
    return actions


def _install_hook_script(manager_dir: Path) -> None:
    dest = manager_dir / "hook.py"
    src = Path(__file__).parent.parent / "hook.py"
    if src.exists():
        shutil.copy2(src, dest)
    else:
        dest.write_text("#!/usr/bin/env python3\nimport sys\nprint('{}')\nsys.exit(0)\n", encoding="utf-8")


def _prompt_yes(rich_msg: str, plain_msg: str | None = None, default: bool = True) -> bool:
    """Print rich_msg with markup, then prompt with plain yes/no."""
    try:
        if rich_msg:
            console.print(rich_msg, end="")
        return typer.confirm(plain_msg or "", default=default)
    except Exception:
        return default


# ── Steps ──────────────────────────────────────────────────────────────────────

def _step1_detect(dry_run: bool) -> None:
    _step(1, 5, "Detecting environment")
    found = lambda v: "[bright_green]found[/bright_green]" if v else "[dim]not found[/dim]"
    rc, py = run_cmd("python3 --version", timeout=5)
    rows = [
        ("Claude config", found(ctx_mod.CLAUDE_DIR.exists())),
        ("settings.json", found(ctx_mod.SETTINGS_PATH.exists())),
        ("Python",        f"[bright_white]{py}[/bright_white]" if rc == 0 else "[dim]not found[/dim]"),
        ("cargo",         found(bool(shutil.which("cargo")))),
        ("npm",           found(bool(shutil.which("npm")))),
    ]
    for label, val in rows:
        console.print(f"  [bright_cyan]◆[/bright_cyan] {label:<16} {val}")


def _step2_backup(dry_run: bool) -> None:
    _step(2, 5, "Backing up config")
    if not ctx_mod.SETTINGS_PATH.exists():
        dim_info("No settings.json — skipping.")
        return
    if not dry_run:
        bpath = settings_mod.backup_create()
        console.print(f"  [bright_green]✓[/bright_green]  {str(bpath).replace(str(Path.home()), '~')}")
    else:
        dim_info("[DRY RUN] would back up settings.json")


def _step3_install_tools(dry_run: bool, minimal: bool, yes: bool) -> list[str]:
    _step(3, 5, "Installing recommended tools")
    if minimal:
        dim_info("--minimal: skipping.")
        return []

    ctx = get_ctx()
    recommended = [t for t in ctx.registry if t.get("tier") == "recommended"]
    if not recommended:
        dim_info("No recommended tools in registry.")
        return []

    installable, already_done = [], []
    tbl = Table(box=box.SIMPLE_HEAVY, border_style="cyan", expand=True, padding=(0, 1))
    tbl.add_column("#", style="dim", width=3)
    tbl.add_column("TOOL", style="bright_white", min_width=14)
    tbl.add_column("DESCRIPTION", min_width=30)
    tbl.add_column("METHOD", style="dim", min_width=8)
    tbl.add_column("STATUS", min_width=10)

    with console.status("[bright_cyan]Detecting...[/bright_cyan]", spinner="dots12"):
        for i, t in enumerate(recommended, 1):
            name = t.get("name", "?")
            methods = t.get("install_methods", [])
            method_type = (methods[0] if methods else {}).get("type", "unknown")
            already = name in ctx.installed.get("tools", {}) or _detect_tool(t)
            if already:
                already_done.append(name)
                status_str = "[dim]installed[/dim]"
            else:
                installable.append(t)
                status_str = "[bright_cyan]?[/bright_cyan]"
            tbl.add_row(str(i), name, f"[dim]{(t.get('description') or '')[:44]}[/dim]", method_type, status_str)

    console.print(tbl)
    if not installable:
        console.print("  [bright_green]✓[/bright_green]  All recommended tools already installed.")
        return []
    if dry_run:
        dim_info(f"[DRY RUN] would install: {', '.join(t['name'] for t in installable)}")
        return []

    if yes:
        approved = list(installable)
        for t in approved:
            console.print(f"  [bright_green]✓[/bright_green]  {t['name']}")
    else:
        # Toggle list — all ON by default, user types numbers to toggle off
        selected = {i for i in range(len(installable))}
        while True:
            console.print()
            for i, t in enumerate(installable):
                name = t["name"]
                method = (t.get("install_methods") or [{}])[0].get("type", "manual")
                mark = "[bright_green][✓][/bright_green]" if i in selected else "[dim][ ][/dim]"
                console.print(f"  {mark} [bright_cyan]{i + 1}[/bright_cyan]  [bright_white]{name:<18}[/bright_white] [dim]{method}[/dim]")
            console.print()
            console.print("  [dim]Toggle by number (e.g. 2 5), Enter to confirm:[/dim]", end=" ")
            try:
                raw = input().strip()
            except (KeyboardInterrupt, EOFError):
                selected.clear()
                break
            if not raw:
                break
            for tok in raw.replace(",", " ").split():
                try:
                    idx = int(tok) - 1
                    if 0 <= idx < len(installable):
                        selected.symmetric_difference_update({idx})
                except ValueError:
                    pass
        approved = [installable[i] for i in sorted(selected)]

    if not approved:
        dim_info("Nothing selected.")
        return []

    results: dict[str, tuple[bool, str]] = {}
    write_lock = threading.Lock()

    def _install_one(t: dict) -> tuple[str, bool, str]:
        name = t["name"]
        method = (t.get("install_methods") or [{}])[0]
        mtype = method.get("type", "unknown")
        try:
            if mtype in ("github_action", "manual"):
                with write_lock:
                    ctx.record_installed(name, "manual")
                    ctx.store.append("install", tool=name, version="latest", method="manual")
                return name, True, "noted (manual)"
            elif mtype == "mcp":
                mcp_cfg = method.get("mcp_config", {})
                if not mcp_cfg and method.get("command"):
                    parts = method["command"].split()
                    mcp_cfg = {"command": parts[0], "args": parts[1:]}
                with write_lock:
                    settings_mod.merge_mcp(name, mcp_cfg)
                    ctx.record_installed(name, "mcp")
                    ctx.store.append("install", tool=name, version="latest", method="mcp")
                return name, True, "added to mcpServers"
            elif mtype in ("cargo", "npm", "go", "pip", "brew", "plugin"):
                cmd = method.get("command")
                if not cmd:
                    return name, False, f"no command for {mtype}"
                rc, out = run_cmd(cmd, timeout=120)
                if rc != 0:
                    return name, False, out[:80]
                with write_lock:
                    ctx.record_installed(name, mtype)
                    ctx.store.append("install", tool=name, version="latest", method=mtype)
                return name, True, f"via {mtype}"
            return name, False, f"unknown: {mtype}"
        except Exception as e:
            return name, False, str(e)[:80]

    with Progress(SpinnerColumn(), TextColumn("[bright_cyan]{task.description}[/bright_cyan]"),
                  BarColumn(bar_width=20), TaskProgressColumn(), console=console) as prog:
        overall = prog.add_task("Installing...", total=len(approved))
        tids = {t["name"]: prog.add_task(f"[dim]{t['name']}[/dim]", total=1) for t in approved}
        with ThreadPoolExecutor(max_workers=min(4, len(approved))) as pool:
            for future in as_completed({pool.submit(_install_one, t): t for t in approved}):
                name, ok, msg = future.result()
                results[name] = (ok, msg)
                prog.update(tids[name], completed=1,
                            description=f"[green]✓ {name}[/green]" if ok else f"[red]✗ {name}[/red]")
                prog.advance(overall)

    console.print()
    installed: list[str] = []
    for name, (ok, msg) in results.items():
        icon = "[bright_green]✓[/bright_green]" if ok else "[bright_red]✗[/bright_red]"
        console.print(f"  {icon}  [bright_white]{name:<18}[/bright_white]  [dim]{msg}[/dim]")
        if ok:
            installed.append(name)
    return installed


def _step4_modules(dry_run: bool, minimal: bool, yes: bool) -> list[str]:
    _step(4, 5, "Enabling modules")
    if minimal or yes:
        for name, desc in MODULES:
            console.print(f"  [bright_green][✓][/bright_green] [bright_white]{name:<10}[/bright_white]  [dim]— {desc}[/dim]")
        return [name for name, _ in MODULES]

    # Show numbered list — all ON by default, user types numbers to toggle off
    selected = {i for i in range(len(MODULES))}
    while True:
        console.print()
        for i, (name, desc) in enumerate(MODULES):
            mark = "[bright_green][✓][/bright_green]" if i in selected else "[dim][ ][/dim]"
            console.print(f"  {mark} [bright_cyan]{i + 1}[/bright_cyan]  [bright_white]{name:<10}[/bright_white]  [dim]— {desc}[/dim]")
        console.print()
        console.print("  [dim]Toggle by number (e.g. 2 4), Enter to confirm:[/dim]", end=" ")
        try:
            raw = input().strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not raw:
            break
        for tok in raw.replace(",", " ").split():
            try:
                idx = int(tok) - 1
                if 0 <= idx < len(MODULES):
                    selected.symmetric_difference_update({idx})
            except ValueError:
                pass

    enabled = [MODULES[i][0] for i in sorted(selected)]
    console.print()
    for i, (name, desc) in enumerate(MODULES):
        mark = "[bright_green][✓][/bright_green]" if i in selected else "[dim][ ][/dim]"
        console.print(f"  {mark} [bright_white]{name:<10}[/bright_white]  [dim]— {desc}[/dim]")
    return enabled


def _step5_config(dry_run: bool, manager_dir: Path, config_path: Path) -> dict:
    _step(5, 5, "Writing configuration")
    if dry_run:
        dim_info(f"[DRY RUN] would create {str(manager_dir).replace(str(Path.home()), '~')}/{{store,backups,registry,state}}")
        dim_info(f"[DRY RUN] would write {str(config_path).replace(str(Path.home()), '~')}")
        dim_info(f"[DRY RUN] would register hooks: {', '.join(HOOK_EVENTS)}")
        return {}

    for sub in ("store", "backups", "registry", "state"):
        (manager_dir / sub).mkdir(parents=True, exist_ok=True)
    console.print(f"  [bright_green]✓[/bright_green]  directories")

    if not config_path.exists():
        config_path.write_text(cfg.to_toml(), encoding="utf-8")
    console.print(f"  [bright_green]✓[/bright_green]  {str(config_path).replace(str(Path.home()), '~')}")

    _install_hook_script(manager_dir)
    console.print(f"  [bright_green]✓[/bright_green]  hook.py")

    hooks: dict = {}
    for event in HOOK_EVENTS:
        hooks.update(_build_hook_entry(event))
    settings_mod.merge_hooks(hooks)
    console.print(f"  [bright_green]✓[/bright_green]  {len(HOOK_EVENTS)} hooks → settings.json")

    for action in _install_skills(claude_dir=ctx_mod.CLAUDE_DIR, dry_run=False):
        console.print(f"  [bright_green]✓[/bright_green]  {action}")

    return {"hooks_merged": len(HOOK_EVENTS)}


# ── Main ───────────────────────────────────────────────────────────────────────

def run_init(dry_run: bool = False, minimal: bool = False, yes: bool = False) -> None:
    header("cc-manager init")
    if dry_run:
        console.print(Panel("[bold yellow]DRY RUN — nothing will be written[/bold yellow]", border_style="yellow"))

    _step1_detect(dry_run)
    _step2_backup(dry_run)
    installed_tools = _step3_install_tools(dry_run, minimal, yes)
    enabled_modules = _step4_modules(dry_run, minimal, yes)
    summary = _step5_config(dry_run, ctx_mod.MANAGER_DIR, ctx_mod.CONFIG_PATH)

    if dry_run:
        dim_info("[DRY RUN] No files written.")
        return

    ctx_mod.invalidate_ctx()
    ctx = get_ctx()
    ctx.store.append("init", minimal=minimal)

    console.print()
    console.print(Panel(
        f"  [bright_green]✓[/bright_green]  {len(installed_tools)} tools installed\n"
        f"  [bright_green]✓[/bright_green]  {summary.get('hooks_merged', len(HOOK_EVENTS))} hooks registered\n"
        f"  [bright_green]✓[/bright_green]  {len(enabled_modules)} modules enabled",
        title="[bold bright_cyan]◉ DONE[/bold bright_cyan]",
        border_style="bright_cyan",
        box=box.DOUBLE_EDGE,
    ))
    console.print("\n  [dim]Run[/dim] [bright_cyan]ccm status[/bright_cyan] [dim]to verify.[/dim]\n")


app = typer.Typer()

@app.command("init")
def init_cmd(
    dry_run: bool = typer.Option(False, "--dry-run"),
    minimal: bool = typer.Option(False, "--minimal"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Initialize cc-manager: create dirs, config, register hooks."""
    run_init(dry_run=dry_run, minimal=minimal, yes=yes)
