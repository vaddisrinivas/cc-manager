"""cc-manager CLI — 8 commands, one file."""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from cc_manager import __version__, registry, settings, installer
from cc_manager.installer import (
    ToolNotFoundError, AlreadyInstalledError, ConflictError, InstallError,
    run_cmd, load_installed,
)
from cc_manager.paths import MANAGER_DIR, INSTALLED_PATH, SETTINGS_PATH

app = typer.Typer(
    name="ccm",
    help="cc-manager — nvm for Claude Code. Install tools, wire hooks, manage your setup.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_hook_config() -> dict:
    """Build the hooks dict to wire into settings.json."""
    hook_cmd = f"{sys.executable} -m cc_manager.hooks"
    return {
        "SessionStart": [
            {"matcher": "", "hooks": [{"type": "command", "command": f"{hook_cmd} SessionStart", "timeout": 10000}]}
        ],
        "SessionEnd": [
            {"matcher": "", "hooks": [{"type": "command", "command": f"{hook_cmd} SessionEnd", "timeout": 30000}]}
        ],
    }


def _err(msg: str) -> None:
    console.print(f"[red]Error:[/red] {msg}")


def _ok(msg: str) -> None:
    console.print(f"[green]{msg}[/green]")


# ---------------------------------------------------------------------------
# ccm init
# ---------------------------------------------------------------------------

@app.command()
def init(
    yes: bool = typer.Option(False, "--yes", "-y", help="Accept defaults, skip prompts"),
    quick: bool = typer.Option(False, "--quick", help="Minimal profile, no prompts"),
) -> None:
    """Set up cc-manager — pick a profile, install tools, wire hooks."""
    profs = registry.profiles()
    tools_map = registry.as_map()

    if quick:
        profile_name = "minimal"
        yes = True
    elif yes:
        profile_name = "recommended"
    else:
        console.print("\n[bold]Available profiles:[/bold]\n")
        for name, info in profs.items():
            count = len(info["tools"])
            console.print(f"  [cyan]{name:15}[/cyan] {count:3} tools  {info['description']}")
        console.print()
        profile_name = typer.prompt("Profile", default="recommended")

    if profile_name not in profs:
        _err(f"Unknown profile '{profile_name}'. Available: {', '.join(profs)}")
        raise typer.Exit(1)

    tool_names = profs[profile_name]["tools"]
    console.print(f"\n[bold]Installing profile [cyan]{profile_name}[/cyan] ({len(tool_names)} tools)...[/bold]\n")

    installed = load_installed()
    succeeded, failed = 0, 0

    for name in tool_names:
        try:
            with console.status(f"[bright_cyan]Installing {name}...[/bright_cyan]"):
                mtype = installer.install_tool(name, tools_map, installed, dry_run=False)
            console.print(f"  [green]+[/green] {name} [dim]({mtype})[/dim]")
            installed = load_installed()  # refresh
            succeeded += 1
        except AlreadyInstalledError:
            console.print(f"  [dim]~ {name} (already installed)[/dim]")
            succeeded += 1
        except (ConflictError, InstallError, ToolNotFoundError) as e:
            console.print(f"  [red]x[/red] {name}: {e}")
            failed += 1

    # Wire hooks
    settings.merge_hooks(_build_hook_config())

    console.print(f"\n[bold green]Done![/bold green] {succeeded} installed, {failed} failed.")
    console.print("[dim]Hooks wired into ~/.claude/settings.json[/dim]\n")


# ---------------------------------------------------------------------------
# ccm install <tool>
# ---------------------------------------------------------------------------

@app.command()
def install(
    name: str = typer.Argument(..., help="Tool name from registry"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would happen"),
) -> None:
    """Install a single tool from the registry."""
    tools_map = registry.as_map()
    installed = load_installed()

    try:
        mtype = installer.install_tool(name, tools_map, installed, dry_run=dry_run)
    except (ToolNotFoundError, AlreadyInstalledError, ConflictError, InstallError) as e:
        _err(str(e))
        raise typer.Exit(1)

    if dry_run:
        console.print(f"[dim]Would install '{name}' via {mtype}[/dim]")
    else:
        _ok(f"Installed {name} ({mtype})")


# ---------------------------------------------------------------------------
# ccm remove <tool>
# ---------------------------------------------------------------------------

@app.command()
def remove(
    name: str = typer.Argument(..., help="Tool name to remove"),
) -> None:
    """Remove an installed tool."""
    installed = load_installed()
    try:
        installer.remove_tool(name, installed)
    except ToolNotFoundError as e:
        _err(str(e))
        raise typer.Exit(1)
    _ok(f"Removed {name}")


# ---------------------------------------------------------------------------
# ccm list
# ---------------------------------------------------------------------------

@app.command("list")
def list_cmd(
    installed_only: bool = typer.Option(False, "--installed", "-i", help="Only show installed tools"),
    tier: str | None = typer.Option(None, "--tier", "-t", help="Filter by tier"),
) -> None:
    """Browse the tool registry."""
    if installed_only:
        inst = load_installed()
        tool_names = list(inst.get("tools", {}).keys())
        if not tool_names:
            console.print("[dim]No tools installed.[/dim]")
            return
        table = Table(title="Installed Tools", box=box.SIMPLE_HEAVY)
        table.add_column("Name", style="cyan")
        table.add_column("Method", style="dim")
        table.add_column("Installed", style="dim")
        for n in sorted(tool_names):
            info = inst["tools"][n]
            table.add_row(n, info.get("method", "?"), info.get("installed_at", "?")[:10])
        console.print(table)
        return

    tools = registry.filter_tools(tier=tier)
    table = Table(title=f"Registry ({len(tools)} tools)", box=box.SIMPLE_HEAVY)
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Tier", style="magenta")
    table.add_column("Category")
    table.add_column("Description", max_width=50)

    for t in tools:
        table.add_row(
            t["name"],
            t.get("tier", ""),
            t.get("category", ""),
            (t.get("description", "")[:47] + "...") if len(t.get("description", "")) > 50 else t.get("description", ""),
        )
    console.print(table)


# ---------------------------------------------------------------------------
# ccm search <query>
# ---------------------------------------------------------------------------

@app.command()
def search(
    query: str = typer.Argument(..., help="Search term"),
) -> None:
    """Search the tool registry."""
    results = registry.search(query)
    if not results:
        console.print(f"[dim]No tools matching '{query}'[/dim]")
        return
    table = Table(title=f"Search: {query} ({len(results)} results)", box=box.SIMPLE_HEAVY)
    table.add_column("Name", style="cyan")
    table.add_column("Tier", style="magenta")
    table.add_column("Description", max_width=60)
    for t in results:
        table.add_row(t["name"], t.get("tier", ""), t.get("description", "")[:60])
    console.print(table)


# ---------------------------------------------------------------------------
# ccm status
# ---------------------------------------------------------------------------

@app.command()
def status() -> None:
    """Show installed tools and hook health."""
    installed = load_installed()
    tool_count = len(installed.get("tools", {}))

    # Check hooks
    s = settings.read()
    hooks = s.get("hooks", {})
    hook_events = [e for e in hooks if any(
        ".cc-manager" in h.get("command", "") or "cc_manager" in h.get("command", "")
        for entry in hooks[e] for h in entry.get("hooks", [])
    )]

    console.print(Panel(
        f"[bold]Tools installed:[/bold] {tool_count}\n"
        f"[bold]Hooks wired:[/bold]    {', '.join(hook_events) if hook_events else '[dim]none[/dim]'}\n"
        f"[bold]Settings:[/bold]       {SETTINGS_PATH}\n"
        f"[bold]Data dir:[/bold]       {MANAGER_DIR}",
        title="[bold cyan]cc-manager status[/bold cyan]",
        box=box.ROUNDED,
    ))


# ---------------------------------------------------------------------------
# ccm doctor
# ---------------------------------------------------------------------------

@app.command()
def doctor() -> None:
    """Run diagnostic checks."""
    installed = load_installed()
    tools_map = registry.as_map()
    tool_names = list(installed.get("tools", {}).keys())
    checks: list[tuple[str, bool, str]] = []

    # Check settings.json exists
    checks.append(("settings.json", SETTINGS_PATH.exists(), str(SETTINGS_PATH)))

    # Check hooks wired
    s = settings.read()
    has_hooks = any(
        "cc_manager" in h.get("command", "")
        for hooks_list in s.get("hooks", {}).values()
        for entry in hooks_list for h in entry.get("hooks", [])
    )
    checks.append(("Hooks wired", has_hooks, "SessionStart + SessionEnd in settings.json"))

    # Check installed.json
    checks.append(("installed.json", INSTALLED_PATH.exists(), str(INSTALLED_PATH)))

    # Detect tools in PATH (parallel)
    missing: list[str] = []
    if tool_names:
        def _check(n: str) -> str | None:
            tool = tools_map.get(n)
            if not tool:
                return None
            cmd = tool.get("detect", {}).get("command", "")
            if not cmd:
                return None
            rc, _ = run_cmd(cmd, timeout=3)
            return n if rc != 0 else None

        with ThreadPoolExecutor(max_workers=min(8, len(tool_names))) as pool:
            for result in pool.map(_check, tool_names):
                if result:
                    missing.append(result)

    checks.append(("All tools detected", len(missing) == 0,
                    f"Missing: {', '.join(missing)}" if missing else f"{len(tool_names)} tools OK"))

    # Print results
    table = Table(title="Doctor", box=box.SIMPLE_HEAVY)
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail", style="dim")
    for label, ok, detail in checks:
        status_str = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
        table.add_row(label, status_str, detail)
    console.print(table)


# ---------------------------------------------------------------------------
# ccm reset
# ---------------------------------------------------------------------------

@app.command()
def reset(
    confirm: bool = typer.Option(False, "--confirm", help="Required to actually reset"),
) -> None:
    """Reset cc-manager — wipe installed state and re-run init."""
    if not confirm:
        console.print("Pass [bold]--confirm[/bold] to wipe installed tools and re-init.")
        raise typer.Exit(1)

    # Wipe state
    if INSTALLED_PATH.exists():
        INSTALLED_PATH.unlink()
        console.print(f"[dim]Removed {INSTALLED_PATH}[/dim]")

    settings.remove_hooks()
    console.print("[dim]Removed cc-manager hooks from settings.json[/dim]")

    # Re-init minimal
    init(yes=True, quick=False)


# ---------------------------------------------------------------------------
# Version callback
# ---------------------------------------------------------------------------

def _version_callback(value: bool) -> None:
    if value:
        console.print(f"cc-manager {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-V", callback=_version_callback, is_eager=True),
) -> None:
    """cc-manager — nvm for Claude Code."""
