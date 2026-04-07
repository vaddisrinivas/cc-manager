"""cc-manager install command."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich import box
from rich.panel import Panel
from rich.padding import Padding
from rich.rule import Rule

import cc_manager.context as ctx_mod
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


def _save_installed(data: dict) -> None:
    path = ctx_mod.REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def install_tool(name: str, dry_run: bool = False) -> None:
    """Install a tool by name. Raises on error."""
    ctx = get_ctx()

    # Find tool in registry
    tool = next((t for t in ctx.registry if t["name"] == name), None)
    if tool is None:
        raise ToolNotFoundError(f"Tool '{name}' not found in registry.")

    # Check if already installed
    installed = ctx.installed
    if name in installed.get("tools", {}):
        raise AlreadyInstalledError(f"Tool '{name}' is already installed.")

    # Check conflicts
    for conflict in tool.get("conflicts_with", []):
        if conflict in installed.get("tools", {}):
            raise ConflictError(
                f"Tool '{name}' conflicts with installed tool '{conflict}'."
            )

    install_methods = tool.get("install_methods", [])
    if not install_methods:
        raise InstallError(f"No install methods for '{name}'.")

    # Pick first method
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
        with console.status(f"[bright_cyan]◆ Installing {name}...[/bright_cyan]", spinner="dots12"):
            rc, output = run_cmd(cmd)
        if rc != 0:
            raise InstallError(f"Install command failed (rc={rc}): {output}")
        _record_installed(name, method_type, ctx)

    elif method_type == "mcp":
        mcp_config = method.get("mcp_config", {})
        if not mcp_config and method.get("command"):
            # Parse command into mcp_config
            parts = method["command"].split()
            mcp_config = {"command": parts[0], "args": parts[1:]}
        settings_mod.merge_mcp(name, mcp_config)
        _record_installed(name, "mcp", ctx)

    elif method_type == "plugin":
        cmd = method.get("command")
        if cmd:
            with console.status(f"[bright_cyan]◆ Installing plugin {name}...[/bright_cyan]", spinner="dots12"):
                rc, output = run_cmd(cmd)
            if rc != 0:
                raise InstallError(f"Plugin install failed (rc={rc}): {output}")
        _record_installed(name, "plugin", ctx)

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
        _record_installed(name, "manual", ctx)

    else:
        raise InstallError(f"Unknown method type '{method_type}'.")

    # Log event
    ctx.store.append("install", tool=name, version="latest", method=method_type)

    console.print()
    console.print(Rule(style="bright_green"))
    success(f"Installed [magenta]{name}[/magenta]  [dim]via {method_type}[/dim]")
    info(f"Registered in [dim]~/.cc-manager/registry/installed.json[/dim]")
    console.print(Rule(style="bright_green"))
    console.print()


def _record_installed(name: str, method: str, ctx) -> None:
    """Update installed.json with new tool entry."""
    installed = ctx.installed
    tools = installed.setdefault("tools", {})
    tools[name] = {
        "version": "latest",
        "method": method,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "pinned": False,
    }
    _save_installed(installed)
    # Refresh ctx.installed
    ctx.installed = installed


app = typer.Typer()


@app.command("install")
def install_cmd(
    name: str = typer.Argument(..., help="Tool name to install"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print what would happen, write nothing"),
) -> None:
    """Install a tool from the registry."""
    # ── Header card ───────────────────────────────────────────────────────────
    ctx = get_ctx()
    tool = next((t for t in ctx.registry if t["name"] == name), None)

    if tool:
        method_str = tool.get("install_methods", [{}])[0].get("command", "—") if tool.get("install_methods") else "—"
        method_type = tool.get("install_methods", [{}])[0].get("type", "—") if tool.get("install_methods") else "—"
        repo = tool.get("repo", "—")
        desc = tool.get("description", "")
        category = tool.get("category", "—")
        tier = tool.get("tier", "—")

        card_body = (
            f"  [bright_white]{desc}[/bright_white]\n"
            f"  [dim]{'─' * 44}[/dim]\n"
            f"  [dim]Method:[/dim]    [bright_cyan]{method_str}[/bright_cyan]\n"
            f"  [dim]Category:[/dim]  [magenta]{category}[/magenta]  ·  [dim]tier:[/dim] [bright_white]{tier}[/bright_white]\n"
            f"  [dim]Repo:[/dim]      [dim]{repo}[/dim]"
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
        install_tool(name, dry_run=dry_run)
    except (ToolNotFoundError, AlreadyInstalledError, ConflictError, InstallError) as e:
        error(str(e), hint=f"Run [bright_cyan]ccm list --available[/bright_cyan] to see all tools.")
        raise typer.Exit(1)
