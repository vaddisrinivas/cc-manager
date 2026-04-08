"""cc-manager install command."""
from __future__ import annotations

from datetime import datetime, timezone

import typer
from rich import box
from rich.panel import Panel
from rich.rule import Rule

import cc_manager.settings as settings_mod
from cc_manager.context import get_ctx, run_cmd
from cc_manager.display import console, success, error, info, dim_info


class ToolNotFoundError(Exception):
    pass


class AlreadyInstalledError(Exception):
    pass


class ConflictError(Exception):
    pass


class InstallError(Exception):
    pass


def install_tool(
    name: str,
    dry_run: bool = False,
    tool: dict | None = None,
) -> None:
    """Install a tool by name.

    `tool` may be a pre-resolved registry entry to avoid a second lookup.
    Raises ToolNotFoundError, AlreadyInstalledError, ConflictError, or
    InstallError on failure.
    """
    ctx = get_ctx()

    if tool is None:
        tool = ctx.registry_map.get(name)
    if tool is None:
        raise ToolNotFoundError(f"Tool '{name}' not found in registry.")

    if name in ctx.installed.get("tools", {}):
        raise AlreadyInstalledError(f"Tool '{name}' is already installed.")

    for conflict in tool.get("conflicts_with", []):
        if conflict in ctx.installed.get("tools", {}):
            raise ConflictError(
                f"Tool '{name}' conflicts with installed tool '{conflict}'."
            )

    install_methods = tool.get("install_methods", [])
    if not install_methods:
        raise InstallError(f"No install methods for '{name}'.")

    method = install_methods[0]
    method_type = method.get("type")

    if dry_run:
        dim_info(f"DRY RUN: would install '{name}' via {method_type}")
        if method.get("command"):
            dim_info(f"  Command: {method['command']}")
        return

    if method_type in ("cargo", "npm", "go", "pip", "brew"):
        cmd = method.get("command")
        if not cmd:
            raise InstallError(f"No command for method type '{method_type}'.")
        # Make cargo installs idempotent (cached binaries won't cause re-install failures)
        if method_type == "cargo" and "--force" not in cmd:
            cmd = cmd + " --force"
        with console.status(f"[bright_cyan]◆ Installing {name}...[/bright_cyan]", spinner="dots12"):
            rc, output = run_cmd(cmd)
        if rc != 0:
            raise InstallError(f"Install command failed (rc={rc}): {output}")
        ctx.record_installed(name, method_type)

    elif method_type == "mcp":
        mcp_config = method.get("mcp_config", {})
        if not mcp_config and method.get("command"):
            parts = method["command"].split()
            mcp_config = {"command": parts[0], "args": parts[1:]}
        settings_mod.merge_mcp(name, mcp_config)
        ctx.record_installed(name, "mcp")

    elif method_type == "plugin":
        cmd = method.get("command")
        if cmd:
            with console.status(f"[bright_cyan]◆ Installing plugin {name}...[/bright_cyan]", spinner="dots12"):
                rc, output = run_cmd(cmd)
            if rc != 0:
                raise InstallError(f"Plugin install failed (rc={rc}): {output}")
        ctx.record_installed(name, "plugin")

    elif method_type in ("github_action", "manual"):
        instructions = method.get("instructions", "See repository for manual install instructions.")
        console.print(
            Panel(
                f"[yellow]{instructions}[/yellow]",
                title="[bold yellow]⚠ MANUAL INSTALL REQUIRED[/bold yellow]",
                border_style="yellow",
                box=box.SIMPLE_HEAVY,
                padding=(0, 2),
            )
        )
        ctx.record_installed(name, "manual")

    else:
        raise InstallError(f"Unknown method type '{method_type}'.")

    ctx.store.append("install", tool=name, version="latest", method=method_type)

    console.print()
    console.print(Rule(style="bright_green"))
    success(f"Installed [magenta]{name}[/magenta]  [dim]via {method_type}[/dim]")
    info(f"Registered in [dim]~/.cc-manager/registry/installed.json[/dim]")
    console.print(Rule(style="bright_green"))
    console.print()


app = typer.Typer()


@app.command("install")
def install_cmd(
    name: str = typer.Argument(..., help="Tool name to install"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print what would happen, write nothing"),
) -> None:
    """Install a tool from the registry."""
    ctx = get_ctx()
    tool = ctx.registry_map.get(name)

    if tool:
        first_method = tool.get("install_methods", [{}])[0] if tool.get("install_methods") else {}
        card_body = (
            f"  [bright_white]{tool.get('description', '')}[/bright_white]\n"
            f"  [dim]{'─' * 44}[/dim]\n"
            f"  [dim]Method:[/dim]    [bright_cyan]{first_method.get('command', '—')}[/bright_cyan]\n"
            f"  [dim]Category:[/dim]  [magenta]{tool.get('category', '—')}[/magenta]  ·  "
            f"[dim]tier:[/dim] [bright_white]{tool.get('tier', '—')}[/bright_white]\n"
            f"  [dim]Repo:[/dim]      [dim]{tool.get('repo', '—')}[/dim]"
        )
        console.print()
        console.print(
            Panel(
                card_body,
                title=f"[bold bright_cyan]◆ Installing {name}[/bold bright_cyan]",
                border_style="cyan",
                box=box.HEAVY,
                padding=(0, 1),
            )
        )
        console.print()

    try:
        install_tool(name, dry_run=dry_run, tool=tool)
    except (ToolNotFoundError, AlreadyInstalledError, ConflictError, InstallError) as e:
        error(str(e), hint="Run [bright_cyan]ccm list --available[/bright_cyan] to see all tools.")
        raise typer.Exit(1)
