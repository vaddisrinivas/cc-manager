"""cc-manager uninstall command."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import typer
from rich.console import Console

import cc_manager.context as ctx_mod
import cc_manager.settings as settings_mod
from cc_manager.context import get_ctx

console = Console()

app = typer.Typer()


def _remove_skills(claude_dir: Path) -> list[str]:
    """Remove cc-manager skill files from ~/.claude/. Returns list of removed paths."""
    removed: list[str] = []

    # Remove ~/.claude/cc-manager.md
    ccm_md = claude_dir / "cc-manager.md"
    if ccm_md.exists():
        ccm_md.unlink()
        removed.append("~/.claude/cc-manager.md")

    # Remove @cc-manager line from ~/.claude/CLAUDE.md
    claude_md = claude_dir / "CLAUDE.md"
    if claude_md.exists():
        lines = claude_md.read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = [l for l in lines if "@cc-manager" not in l]
        if len(new_lines) != len(lines):
            claude_md.write_text("".join(new_lines), encoding="utf-8")
            removed.append("~/.claude/CLAUDE.md (@cc-manager removed)")

    # Remove ~/.claude/skills/cc-manager/ directory
    skills_dir = claude_dir / "skills" / "cc-manager"
    if skills_dir.exists():
        shutil.rmtree(skills_dir)
        removed.append("~/.claude/skills/cc-manager/")

    return removed


@app.command("uninstall")
def uninstall_cmd(
    name: str = typer.Argument(..., help="Tool name to uninstall"),
) -> None:
    """Uninstall a tool."""
    ctx = get_ctx()
    installed = ctx.installed.get("tools", {})
    if name not in installed:
        console.print(f"[yellow]{name} is not installed.[/yellow]")
        raise typer.Exit(1)

    info = installed[name]
    method = info.get("method", "")

    if method == "mcp":
        settings_mod.remove_mcp(name)
        console.print(f"[green]Removed MCP server:[/green] {name}")
    elif method == "plugin":
        console.print(f"[yellow]To remove plugin:[/yellow] claude plugin uninstall {name}")
    else:
        # Find remove_hint from registry
        tool = next((t for t in ctx.registry if t["name"] == name), None)
        hint = tool.get("remove_hint", f"Manually remove the {name} binary.") if tool else f"Manually remove the {name} binary."
        console.print(f"[yellow]To fully remove:[/yellow] {hint}")

    # Remove from installed.json
    del installed[name]
    path = ctx_mod.REGISTRY_PATH
    path.write_text(json.dumps(ctx.installed, indent=2), encoding="utf-8")

    ctx.store.append("uninstall", tool=name)
    console.print(f"[green]Uninstalled[/green] {name}")
