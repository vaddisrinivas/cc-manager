"""cc-manager profile command — save, load, and manage tool profiles."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from cc_manager.display import console, dim_info, success

app = typer.Typer(help="Save and load named sets of tools.")

# ── Profile storage ───────────────────────────────────────────────────────────

def _profiles_dir() -> Path:
    from cc_manager.context import MANAGER_DIR
    d = MANAGER_DIR / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _user_profile_path(name: str) -> Path:
    return _profiles_dir() / f"{name}.json"


def _load_user_profile(name: str) -> dict | None:
    p = _user_profile_path(name)
    return json.loads(p.read_text()) if p.exists() else None


def _save_user_profile(profile: dict) -> None:
    _user_profile_path(profile["name"]).write_text(
        json.dumps(profile, indent=2) + "\n"
    )


# ── Built-in profiles ─────────────────────────────────────────────────────────

_BUILTIN_DEFS: list[tuple[str, str, dict]] = [
    ("recommended", "All recommended-tier tools",
     {"tier": "recommended"}),
    ("minimal", "Core/essential tools only",
     {"tier": "core"}),
    ("security", "Security and auditing tools",
     {"category": "security"}),
    ("data", "Database and analytics tools",
     {"category__in": ["database", "analytics", "data"]}),
    ("browsing", "Browser automation and web tools",
     {"category__in": ["browser", "search", "web"]}),
]


def _matches(tool: dict, filters: dict) -> bool:
    for key, val in filters.items():
        if key.endswith("__in"):
            field = key[:-4]
            if tool.get(field) not in val:
                return False
        else:
            if tool.get(key) != val:
                return False
    return True


def _builtin_tools(filters: dict) -> list[str]:
    from cc_manager.context import get_ctx
    ctx = get_ctx()
    return [t["name"] for t in ctx.registry if _matches(t, filters)]


def _get_builtin(name: str) -> dict | None:
    for bname, desc, filters in _BUILTIN_DEFS:
        if bname == name:
            return {
                "name": bname,
                "description": desc,
                "builtin": True,
                "tools": _builtin_tools(filters),
            }
    return None


def _all_profiles() -> list[dict]:
    """All profiles: builtins first, then user-saved, sorted."""
    profiles = []
    for bname, desc, filters in _BUILTIN_DEFS:
        profiles.append({
            "name": bname,
            "description": desc,
            "builtin": True,
            "tools": _builtin_tools(filters),
        })
    for f in sorted(_profiles_dir().glob("*.json")):
        try:
            p = json.loads(f.read_text())
            if not p.get("builtin"):
                profiles.append(p)
        except (json.JSONDecodeError, OSError):
            pass
    return profiles


# ── Commands ──────────────────────────────────────────────────────────────────

@app.command("list")
def profile_list() -> None:
    """List all available profiles."""
    from cc_manager.context import get_ctx
    ctx = get_ctx()
    installed = set(ctx.installed.get("tools", {}).keys())
    profiles = _all_profiles()

    console.print()
    console.print(Rule("[bold bright_cyan]Profiles[/bold bright_cyan]", style="cyan"))
    console.print()

    tbl = Table(box=box.SIMPLE_HEAVY, border_style="cyan", padding=(0, 1), expand=True)
    tbl.add_column("NAME",        style="bright_white", min_width=16)
    tbl.add_column("TYPE",        style="dim",          width=8)
    tbl.add_column("TOOLS",       style="bright_cyan",  width=7, justify="right")
    tbl.add_column("INSTALLED",   style="bright_green", width=10, justify="right")
    tbl.add_column("DESCRIPTION", style="dim")

    for p in profiles:
        tools = p.get("tools", [])
        have  = sum(1 for t in tools if t in installed)
        kind  = "[dim]builtin[/dim]" if p.get("builtin") else "[bright_cyan]user[/bright_cyan]"
        pct   = f"{have}/{len(tools)}"
        tbl.add_row(p["name"], kind, str(len(tools)), pct, p.get("description", ""))

    console.print(tbl)
    console.print(f"  [dim]Run[/dim] [bright_cyan]ccm profile show <name>[/bright_cyan] [dim]to inspect a profile.[/dim]")
    console.print()


@app.command("show")
def profile_show(
    name: str = typer.Argument(..., help="Profile name"),
) -> None:
    """Show tools in a profile and which are installed."""
    from cc_manager.context import get_ctx
    ctx = get_ctx()
    installed = ctx.installed.get("tools", {})

    profile = _get_builtin(name) or _load_user_profile(name)
    if not profile:
        console.print(f"  [bright_red]✗[/bright_red]  Profile '[bright_white]{name}[/bright_white]' not found.")
        console.print(f"  [dim]Run[/dim] [bright_cyan]ccm profile list[/bright_cyan] [dim]to see available profiles.[/dim]")
        raise typer.Exit(1)

    tools_in_profile = profile.get("tools", [])
    kind = "builtin" if profile.get("builtin") else "user"
    have = sum(1 for t in tools_in_profile if t in installed)

    console.print()
    console.print(Panel(
        f"  [dim]Type:[/dim]        [bright_cyan]{kind}[/bright_cyan]\n"
        f"  [dim]Tools:[/dim]       {len(tools_in_profile)}  "
        f"([bright_green]{have} installed[/bright_green], "
        f"[yellow]{len(tools_in_profile) - have} missing[/yellow])\n"
        f"  [dim]Description:[/dim] {profile.get('description', '—')}",
        title=f"[bold bright_cyan]◆ {name}[/bold bright_cyan]",
        border_style="cyan",
        box=box.SIMPLE_HEAVY,
    ))

    tbl = Table(box=box.SIMPLE_HEAVY, border_style="dim", padding=(0, 1), expand=True)
    tbl.add_column("TOOL",    style="bright_white", min_width=20)
    tbl.add_column("STATUS",  width=12)
    tbl.add_column("METHOD",  style="dim", width=10)

    for t_name in sorted(tools_in_profile):
        info = installed.get(t_name)
        if info:
            status = "[bright_green]✓ installed[/bright_green]"
            method = info.get("method", "—")
        else:
            status = "[yellow]○ missing[/yellow]"
            method = "—"
        tbl.add_row(t_name, status, method)

    console.print(tbl)

    if have < len(tools_in_profile):
        missing = len(tools_in_profile) - have
        console.print(f"  [dim]Run[/dim] [bright_cyan]ccm profile load {name}[/bright_cyan] [dim]to install the {missing} missing tool(s).[/dim]")
    console.print()


@app.command("save")
def profile_save(
    name: str = typer.Argument(..., help="Name for this profile"),
    description: str = typer.Option("", "--desc", "-d", help="Short description"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing profile"),
) -> None:
    """Snapshot currently installed tools as a named profile."""
    if _get_builtin(name):
        console.print(f"  [bright_red]✗[/bright_red]  '{name}' is a built-in profile and cannot be overwritten.")
        raise typer.Exit(1)

    if _user_profile_path(name).exists() and not force:
        console.print(f"  [yellow]![/yellow]  Profile '[bright_white]{name}[/bright_white]' already exists. Use [bright_cyan]--force[/bright_cyan] to overwrite.")
        raise typer.Exit(1)

    from cc_manager.context import get_ctx
    ctx = get_ctx()
    tools = sorted(ctx.installed.get("tools", {}).keys())

    if not tools:
        console.print("  [yellow]![/yellow]  No tools installed — nothing to save.")
        raise typer.Exit(1)

    profile = {
        "name": name,
        "description": description or f"Saved on {datetime.now(timezone.utc).date()}",
        "builtin": False,
        "tools": tools,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_user_profile(profile)

    console.print()
    success(f"Profile '[bright_white]{name}[/bright_white]' saved with {len(tools)} tool(s).")
    dim_info(f"  {', '.join(tools[:8])}{'…' if len(tools) > 8 else ''}")
    console.print()


@app.command("load")
def profile_load(
    name: str = typer.Argument(..., help="Profile to load"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be installed"),
) -> None:
    """Install all tools in a profile (skips already-installed ones)."""
    from cc_manager.context import get_ctx
    from cc_manager.commands.install import install_tool, InstallError

    ctx = get_ctx()
    profile = _get_builtin(name) or _load_user_profile(name)
    if not profile:
        console.print(f"  [bright_red]✗[/bright_red]  Profile '[bright_white]{name}[/bright_white]' not found.")
        raise typer.Exit(1)

    installed = set(ctx.installed.get("tools", {}).keys())
    all_tools = profile.get("tools", [])
    to_install = [t for t in all_tools if t not in installed]

    if not to_install:
        console.print(f"  [bright_green]✓[/bright_green]  All {len(all_tools)} tools in '[bright_white]{name}[/bright_white]' are already installed.")
        return

    registry_by_name = ctx.registry_map
    missing_from_registry = [t for t in to_install if t not in registry_by_name]
    installable = [registry_by_name[t] for t in to_install if t in registry_by_name]

    console.print()
    console.print(Panel(
        f"  [dim]Profile:[/dim]  [bright_white]{name}[/bright_white]\n"
        f"  [dim]To install:[/dim] {len(installable)}  "
        + (f"[dim]({len(missing_from_registry)} not in registry)[/dim]" if missing_from_registry else ""),
        title="[bold bright_cyan]◆ Load Profile[/bold bright_cyan]",
        border_style="cyan", box=box.SIMPLE_HEAVY,
    ))

    if dry_run:
        for t in installable:
            console.print(f"  [dim]would install[/dim] [bright_cyan]{t['name']}[/bright_cyan]")
        return

    if not yes:
        from cc_manager.commands.init import _checkbox_select
        rows = [
            (t["name"], (t.get("install_methods") or [{}])[0].get("type", "manual"))
            for t in installable
        ]
        # Build conflict + badge maps
        name_to_idx = {t["name"]: i for i, t in enumerate(installable)}
        conflicts_map: dict[int, list[str]] = {}
        badges_map: dict[int, str] = {}
        for i, t in enumerate(installable):
            cw = t.get("conflicts_with", [])
            if cw:
                conflicts_map[i] = [c for c in cw if c in name_to_idx]
            api_key = t.get("needs_api_key", "")
            if api_key:
                badges_map[i] = api_key
        idxs = _checkbox_select(
            rows, title=f"Select tools to install from profile '{name}'",
            conflicts=conflicts_map, badges=badges_map,
        )
        installable = [installable[i] for i in sorted(idxs)]

    if not installable:
        dim_info("Nothing selected.")
        return

    ok_count = 0
    for tool_entry in installable:
        t_name = tool_entry["name"]
        try:
            install_tool(t_name, dry_run=False, tool=tool_entry)
            ok_count += 1
        except Exception as exc:
            console.print(f"  [bright_red]✗[/bright_red]  {t_name}  [dim]{exc}[/dim]")

    console.print()
    success(f"Installed {ok_count}/{len(installable)} tools from profile '[bright_white]{name}[/bright_white]'.")
    console.print()


@app.command("diff")
def profile_diff(
    name: str = typer.Argument(..., help="Profile to compare against"),
) -> None:
    """Show what differs between current install and a profile."""
    from cc_manager.context import get_ctx
    ctx = get_ctx()
    profile = _get_builtin(name) or _load_user_profile(name)
    if not profile:
        console.print(f"  [bright_red]✗[/bright_red]  Profile '[bright_white]{name}[/bright_white]' not found.")
        raise typer.Exit(1)

    installed = set(ctx.installed.get("tools", {}).keys())
    profile_tools = set(profile.get("tools", []))

    only_installed = sorted(installed - profile_tools)
    only_profile   = sorted(profile_tools - installed)
    both           = sorted(installed & profile_tools)

    console.print()
    console.print(Rule(f"[bold bright_cyan]diff: current ↔ {name}[/bold bright_cyan]", style="cyan"))
    console.print()

    if not only_installed and not only_profile:
        console.print("  [bright_green]✓[/bright_green]  Current install matches profile exactly.")
        console.print()
        return

    if only_profile:
        console.print(f"  [yellow]○[/yellow]  In profile, not installed ({len(only_profile)}):")
        for t in only_profile:
            console.print(f"      [yellow]+[/yellow] {t}")
        console.print()

    if only_installed:
        console.print(f"  [dim]●[/dim]  Installed, not in profile ({len(only_installed)}):")
        for t in only_installed:
            console.print(f"      [dim]-[/dim] {t}")
        console.print()

    console.print(f"  [dim]Both:[/dim] {len(both)} tool(s) match")
    if only_profile:
        console.print(f"\n  [dim]Run[/dim] [bright_cyan]ccm profile load {name}[/bright_cyan] [dim]to install missing tools.[/dim]")
    console.print()


@app.command("delete")
def profile_delete(
    name: str = typer.Argument(..., help="Profile to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete a user-saved profile."""
    if _get_builtin(name):
        console.print(f"  [bright_red]✗[/bright_red]  '[bright_white]{name}[/bright_white]' is a built-in profile and cannot be deleted.")
        raise typer.Exit(1)

    path = _user_profile_path(name)
    if not path.exists():
        console.print(f"  [bright_red]✗[/bright_red]  Profile '[bright_white]{name}[/bright_white]' not found.")
        raise typer.Exit(1)

    if not yes:
        typer.confirm(f"Delete profile '{name}'?", abort=True)

    path.unlink()
    success(f"Profile '[bright_white]{name}[/bright_white]' deleted.")
