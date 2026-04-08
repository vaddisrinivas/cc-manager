"""cc-manager list command."""
from __future__ import annotations

from typing import Optional

import typer
from rich import box
from rich.padding import Padding
from rich.table import Table

from cc_manager.context import get_ctx
from cc_manager.display import console
from cc_manager.theme import tier_label

app = typer.Typer()


def get_tools_list(
    installed_only: bool = False,
    available_only: bool = False,
    category: Optional[str] = None,
    tier: Optional[str] = None,
) -> list[dict]:
    """Return tools list with install status merged in."""
    ctx = get_ctx()
    installed_names = set(ctx.installed.get("tools", {}).keys())

    results = []
    for tool in ctx.registry:
        name = tool["name"]
        is_installed = name in installed_names

        if installed_only and not is_installed:
            continue
        if available_only and is_installed:
            continue
        if category and tool.get("category") != category:
            continue
        if tier and tool.get("tier") != tier:
            continue

        entry = dict(tool)
        entry["installed"] = is_installed
        if is_installed:
            info = ctx.installed["tools"][name]
            entry["installed_version"] = info.get("version", "unknown")
            entry["installed_at"] = info.get("installed_at", "")
        results.append(entry)

    return results


@app.command("list")
def list_cmd(
    installed: bool = typer.Option(False, "--installed", help="Show only installed tools"),
    available: bool = typer.Option(False, "--available", help="Show only not-installed tools"),
    category: Optional[str] = typer.Option(None, "--category", help="Filter by category"),
    tier: Optional[str] = typer.Option(None, "--tier", help="Filter by tier"),
) -> None:
    """List tools in the registry."""
    tools = get_tools_list(
        installed_only=installed,
        available_only=available,
        category=category,
        tier=tier,
    )

    console.print()

    for tool in tools:
        if tool.get("installed"):
            mark = "[bright_green]✓[/bright_green]"
            name = f"[bright_white]{tool['name']}[/bright_white]"
        else:
            mark = "[dim]○[/dim]"
            name = f"{tool['name']}"
        tier = tier_label(tool.get("tier", ""))
        cat = f"[dim]{tool.get('category', '')}[/dim]"
        console.print(f"  {mark} {name:<24} {tier:<28} {cat}")

    console.print(f"\n  [dim]{len(tools)} tools[/dim]")
    console.print()
