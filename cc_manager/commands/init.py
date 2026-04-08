"""cc-manager init command."""
from __future__ import annotations

import shutil
import sys
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


# ── Interactive checkbox ───────────────────────────────────────────────────────

_ESC   = "\x1b"
_HIDE  = "\x1b[?25l"
_SHOW  = "\x1b[?25h"
_CLR   = "\x1b[2K\r"
_GREEN = "\x1b[92m"
_DIM   = "\x1b[2m"
_BOLD  = "\x1b[1;97m"
_CYAN  = "\x1b[96m"
_RST   = "\x1b[0m"
_UP    = lambda n: f"\x1b[{n}A" if n > 0 else ""


_YELLOW = "\x1b[93m"
_RED    = "\x1b[91m"


def _checkbox_select(
    rows: list[tuple[str, str]],  # (label, hint) pairs
    title: str = "",
    default_on: bool = True,
    visible: int = 18,
    conflicts: dict[int, list[str]] | None = None,  # idx → list of conflicting names
    badges: dict[int, str] | None = None,            # idx → badge like "🔑 GITHUB_TOKEN"
) -> set[int]:
    """
    Arrow-key navigable checkbox prompt with conflict warnings and badges.
    Returns set of selected indices, or full set on non-TTY / import error.
    Keys: ↑↓ move · space toggle · a all/none · enter confirm · q/^C cancel
    """
    if not sys.stdin.isatty():
        return set(range(len(rows))) if default_on else set()

    try:
        import tty, termios  # noqa: F401
    except ImportError:
        return set(range(len(rows))) if default_on else set()

    import tty, termios  # noqa: F811

    conflicts = conflicts or {}
    badges = badges or {}
    N = len(rows)
    selected: set[int] = set(range(N)) if default_on else set()
    cursor = 0
    scroll = 0
    visible = min(visible, N)
    rendered = 0

    # Build name→index lookup for conflict resolution
    name_to_idx: dict[str, int] = {rows[i][0]: i for i in range(N)}

    def _active_conflicts(idx: int) -> list[str]:
        """Return names of selected tools that conflict with rows[idx]."""
        conf_names = conflicts.get(idx, [])
        return [cn for cn in conf_names if name_to_idx.get(cn, -1) in selected]

    def _render() -> None:
        nonlocal rendered
        lines: list[str] = []
        if title:
            lines.append(f"  {_DIM}{title}{_RST}")
        for i in range(scroll, scroll + visible):
            if i >= N:
                lines.append("")
                continue
            label, hint = rows[i]
            check = f"{_GREEN}[✓]{_RST}" if i in selected else f"{_DIM}[ ]{_RST}"
            ptr   = f"{_CYAN}›{_RST}" if i == cursor else " "
            name  = f"{_BOLD}{label:<18}{_RST}" if i == cursor else f"{label:<18}"
            hint_ = f"{_DIM}{hint}{_RST}"
            line  = f"  {ptr} {check} {name} {hint_}"

            # Show badge (API key needed)
            badge = badges.get(i, "")
            if badge:
                line += f"  {_YELLOW}⚙ {badge}{_RST}"

            # Show conflict warning if this AND a conflicting tool are both selected
            if i in selected:
                active = _active_conflicts(i)
                if active:
                    line += f"  {_RED}⚠ overlaps {', '.join(active[:2])}{_RST}"

            lines.append(line)
        if N > visible:
            shown_end = scroll + visible
            lines.append(f"  {_DIM}── {scroll + 1}–{min(shown_end, N)} of {N}  (↑↓ scroll){_RST}")
        lines.append("")  # blank spacer
        lines.append(f"  {_DIM}↑↓ move · space toggle · a all/none · enter confirm{_RST}")
        buf = ""
        if rendered:
            buf += _UP(rendered)
        for ln in lines:
            buf += _CLR + ln + "\n"
        rendered = len(lines)
        sys.stdout.write(buf)
        sys.stdout.flush()

    sys.stdout.write(_HIDE + "\n")
    sys.stdout.flush()
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)

    try:
        tty.setcbreak(fd)
        _render()
        while True:
            ch = sys.stdin.read(1)
            if ch in ("\r", "\n"):
                break
            if ch == " ":
                selected.symmetric_difference_update({cursor})
            elif ch in ("a", "A"):
                selected = set(range(N)) if len(selected) != N else set()
            elif ch in ("q", "\x03"):
                selected = set()
                break
            elif ch == _ESC:
                seq = sys.stdin.read(2)
                if seq == "[A":  # up
                    cursor = max(0, cursor - 1)
                    if cursor < scroll:
                        scroll = cursor
                elif seq == "[B":  # down
                    cursor = min(N - 1, cursor + 1)
                    if cursor >= scroll + visible:
                        scroll = cursor - visible + 1
            _render()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write(_SHOW)
        sys.stdout.flush()

    return selected


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
        rows = [
            (t["name"], (t.get("install_methods") or [{}])[0].get("type", "manual"))
            for t in installable
        ]
        # Build conflict map and badge map for the checkbox
        name_to_row_idx = {t["name"]: i for i, t in enumerate(installable)}
        conflicts_map: dict[int, list[str]] = {}
        badges_map: dict[int, str] = {}
        for i, t in enumerate(installable):
            cw = t.get("conflicts_with", [])
            if cw:
                conflicts_map[i] = [c for c in cw if c in name_to_row_idx]
            api_key = t.get("needs_api_key", "")
            if api_key:
                badges_map[i] = api_key
        idxs = _checkbox_select(
            rows, title="Space to toggle · Enter to install selected",
            conflicts=conflicts_map, badges=badges_map,
        )
        approved = [installable[i] for i in sorted(idxs)]

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

    rows = [(name, desc) for name, desc in MODULES]
    idxs = _checkbox_select(rows, title="Space to toggle · Enter to enable selected")
    enabled = [MODULES[i][0] for i in sorted(idxs)]
    console.print()
    for i, (name, desc) in enumerate(MODULES):
        mark = "[bright_green][✓][/bright_green]" if i in idxs else "[dim][ ][/dim]"
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

_BANNER = """\
  ██████╗ ██████╗    ███╗   ███╗ █████╗ ███╗  ██╗ █████╗  ██████╗ ███████╗██████╗
 ██╔════╝██╔════╝    ████╗ ████║██╔══██╗████╗ ██║██╔══██╗██╔════╝██╔════╝██╔══██╗
 ██║     ██║         ██╔████╔██║███████║██╔██╗██║███████║██║  ███╗█████╗  ██████╔╝
 ██║     ██║         ██║╚██╔╝██║██╔══██║██║╚████║██╔══██║██║   ██║██╔══╝  ██╔══██╗
 ╚██████╗╚██████╗    ██║ ╚═╝ ██║██║  ██║██║ ╚███║██║  ██║╚██████╔╝███████╗██║  ██║
  ╚═════╝ ╚═════╝    ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚══╝╚═╝  ╚═╝ ╚═════╝╚══════╝╚═╝  ╚═╝"""


def _print_banner() -> None:
    import time
    from rich.live import Live
    from rich.text import Text
    lines = _BANNER.splitlines()
    with Live(Text(""), refresh_per_second=30, console=console) as live:
        for i, line in enumerate(lines):
            live.update(Text("\n".join(lines[:i + 1]), style="bold bright_cyan"))
            time.sleep(0.04)
    console.print()
    msg = "  Initializing cc-manager..."
    with Live(Text(""), refresh_per_second=60, console=console) as live:
        buf = ""
        for ch in msg:
            buf += ch
            live.update(Text(buf, style="bright_cyan"))
            time.sleep(0.025)
    console.print()


def run_init(dry_run: bool = False, minimal: bool = False, yes: bool = False) -> None:
    if not dry_run:
        _print_banner()
    else:
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
