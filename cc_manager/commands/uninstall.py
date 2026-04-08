"""cc-manager uninstall command."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.rule import Rule

import cc_manager.settings as settings_mod
from cc_manager.context import get_ctx
from cc_manager.display import console, dim_info, success

app = typer.Typer()


def _remove_skills(claude_dir: Path) -> list[str]:
    """Remove cc-manager skill files from ~/.claude/. Returns list of removed paths."""
    removed: list[str] = []

    ccm_md = claude_dir / "cc-manager.md"
    if ccm_md.exists():
        ccm_md.unlink()
        removed.append("~/.claude/cc-manager.md")

    claude_md = claude_dir / "CLAUDE.md"
    if claude_md.exists():
        lines = claude_md.read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = [l for l in lines if "@cc-manager" not in l]
        if len(new_lines) != len(lines):
            claude_md.write_text("".join(new_lines), encoding="utf-8")
            removed.append("~/.claude/CLAUDE.md (@cc-manager removed)")

    skills_dir = claude_dir / "skills" / "cc-manager"
    if skills_dir.exists():
        shutil.rmtree(skills_dir)
        removed.append("~/.claude/skills/cc-manager/")

    return removed


def _do_uninstall(name: str, ctx) -> None:
    """Perform the actual uninstall for a single tool."""
    installed = ctx.installed.get("tools", {})
    method = installed[name].get("method", "")

    if method == "mcp":
        settings_mod.remove_mcp(name)
    elif method == "plugin":
        console.print(f"  [dim]hint:[/dim] claude plugin uninstall {name}")
    else:
        tool = ctx.registry_map.get(name)
        hint = (tool.get("remove_hint") or f"Manually remove the {name} binary.") if tool else f"Manually remove the {name} binary."
        console.print(f"  [dim]hint:[/dim] {hint}")

    ctx.remove_installed(name)
    ctx.store.append("uninstall", tool=name)
    console.print(f"  [bright_green]✓[/bright_green]  [bright_white]{name}[/bright_white] [dim]uninstalled[/dim]")


@app.command("uninstall")
def uninstall_cmd(
    name: Optional[str] = typer.Argument(None, help="Tool name to uninstall (interactive picker if omitted)"),
) -> None:
    """Uninstall a tool. Omit NAME for an interactive picker."""
    ctx = get_ctx()
    installed = ctx.installed.get("tools", {})

    if name is None and not installed:
        console.print("  [dim]No tools installed.[/dim]")
        return

    if name is None:
        # Interactive multi-select from installed tools
        from cc_manager.commands.init import _checkbox_select
        rows = [
            (t_name, info.get("method", "—"))
            for t_name, info in sorted(installed.items())
        ]
        console.print()
        console.print(Rule("[bold bright_cyan]Uninstall Tools[/bold bright_cyan]", style="cyan"))
        console.print()
        idxs = _checkbox_select(rows, title="Space to select · Enter to uninstall", default_on=False)
        if not idxs:
            dim_info("Nothing selected.")
            return
        names = [rows[i][0] for i in sorted(idxs)]
        console.print()
        for n in names:
            _do_uninstall(n, ctx)
        return

    if name not in installed:
        console.print(f"  [bright_red]✗[/bright_red]  [bright_white]{name}[/bright_white] is not installed.")
        raise typer.Exit(1)

    _do_uninstall(name, ctx)
