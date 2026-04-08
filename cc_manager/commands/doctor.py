"""cc-manager doctor command."""
from __future__ import annotations

import sys
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

import typer
from rich import box
from rich.panel import Panel
from rich.padding import Padding
from rich.progress import Progress, SpinnerColumn, TextColumn

import cc_manager.context as ctx_mod
from cc_manager.context import get_ctx, run_cmd  # run_cmd imported for test mock-ability
from cc_manager.display import console
from cc_manager.theme import status_icon, status_word
from cc_manager.context import dot_get

app = typer.Typer()

# Exact command to fix each named check failure
_DOCTOR_FIXES: dict[str, str] = {
    "python_version":  "brew install python@3.12",
    "config_valid":    "ccm reset --config --confirm",
    "store_writable":  "mkdir -p ~/.cc-manager/store",
    "hooks_registered": "ccm init",
}


def run_checks() -> dict[str, dict]:
    """Run all doctor checks. Returns dict of check_name -> {status, message}."""
    ctx = get_ctx()
    results: dict[str, dict] = {}

    # Python version
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 11):
        results["python_version"] = {"status": "ok", "message": f"Python {major}.{minor}"}
    else:
        results["python_version"] = {"status": "fail", "message": f"Python {major}.{minor} < 3.11"}

    # Config valid
    config_path = ctx_mod.CONFIG_PATH
    if config_path.exists():
        try:
            if tomllib is None:
                raise ImportError("tomllib/tomli not available")
            tomllib.loads(config_path.read_text(encoding="utf-8"))
            results["config_valid"] = {"status": "ok", "message": f"{config_path} is valid TOML"}
        except Exception as e:
            results["config_valid"] = {"status": "fail", "message": f"Invalid TOML: {e}"}
    else:
        results["config_valid"] = {"status": "warn", "message": "config.toml not found"}

    # Store writable
    store_path = ctx_mod.STORE_PATH
    try:
        store_path.parent.mkdir(parents=True, exist_ok=True)
        test_file = store_path.parent / ".write_test"
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink()
        results["store_writable"] = {"status": "ok", "message": str(store_path.parent)}
    except Exception as e:
        results["store_writable"] = {"status": "fail", "message": str(e)}

    # Hooks registered
    hooks = ctx.settings.get("hooks", {})
    cc_hooks = [
        ev for ev, entries in hooks.items()
        for entry in entries
        for h in entry.get("hooks", [])
        if ".cc-manager" in h.get("command", "")
    ]
    if len(cc_hooks) >= 2:
        results["hooks_registered"] = {"status": "ok", "message": f"{len(cc_hooks)} cc-manager hooks found"}
    elif cc_hooks:
        results["hooks_registered"] = {"status": "warn", "message": f"Only {len(cc_hooks)} cc-manager hooks registered"}
    else:
        results["hooks_registered"] = {"status": "fail", "message": "No cc-manager hooks in settings.json"}

    # Installed tool checks (inline so tests can mock module-level run_cmd)
    for tool_name in ctx.installed.get("tools", {}):
        reg_entry = next((t for t in ctx.registry if t["name"] == tool_name), None)
        if reg_entry is None:
            results[f"tool:{tool_name}"] = {"status": "warn", "message": "Not in registry"}
            continue
        detect = reg_entry.get("detect", {})
        cmd = detect.get("command", "")
        settings_key = detect.get("settings_json_key", "")
        if cmd:
            rc, output = run_cmd(cmd, timeout=3)
            status = "ok" if rc == 0 else "fail"
            results[f"tool:{tool_name}"] = {"status": status, "message": output.strip()[:80]}
        elif settings_key:
            val = dot_get(ctx.settings, settings_key)
            if val is not None:
                results[f"tool:{tool_name}"] = {"status": "ok", "message": f"Found in settings: {settings_key}"}
            else:
                results[f"tool:{tool_name}"] = {"status": "warn", "message": f"Not found in settings: {settings_key}"}
        else:
            results[f"tool:{tool_name}"] = {"status": "ok", "message": "Manual install (no detect)"}

    ctx.store.append("doctor", results={k: v["status"] for k, v in results.items()})
    return results


@app.command("doctor")
def doctor_cmd() -> None:
    """Run diagnostic checks on the cc-manager installation."""
    console.print()
    console.print(
        Panel(
            "[bold bright_cyan]⚡ CC-MANAGER DIAGNOSTIC[/bold bright_cyan]",
            box=box.HEAVY,
            border_style="cyan",
            padding=(0, 2),
        )
    )
    console.print()

    with Progress(
        SpinnerColumn("dots12", style="bright_cyan"),
        TextColumn("[bright_cyan]{task.description}[/bright_cyan]"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Running checks...", total=None)
        results = run_checks()
        progress.update(task, completed=True)

    system_checks = {k: v for k, v in results.items() if not k.startswith("tool:")}
    tool_checks = {k: v for k, v in results.items() if k.startswith("tool:")}

    def _render_rows(checks: dict) -> str:
        lines = []
        for check, info in checks.items():
            icon = status_icon(info["status"])
            label = status_word(info["status"])
            display_name = check.replace("tool:", "").replace("_", " ")
            msg = info.get("message", "")
            lines.append(f"{icon}  [bright_white]{display_name:<24}[/bright_white]  [dim]{msg[:56]}[/dim]")
        return "\n".join(lines) if lines else "  [dim]No checks[/dim]"

    console.print(
        Panel(
            _render_rows(system_checks),
            title="[bold bright_cyan]◆ SYSTEM[/bold bright_cyan]",
            border_style="cyan",
            box=box.SIMPLE_HEAVY,
            padding=(0, 1),
        )
    )

    if tool_checks:
        console.print(
            Panel(
                _render_rows(tool_checks),
                title="[bold bright_cyan]◆ EXTERNAL TOOLS[/bold bright_cyan]",
                border_style="cyan",
                box=box.SIMPLE_HEAVY,
                padding=(0, 1),
            )
        )

    n_ok = sum(1 for v in results.values() if v["status"] == "ok")
    n_warn = sum(1 for v in results.values() if v["status"] == "warn")
    n_fail = sum(1 for v in results.values() if v["status"] == "fail")

    summary_parts = [f"[bright_green]{n_ok} passed[/bright_green]"]
    if n_warn:
        summary_parts.append(f"[yellow]{n_warn} warning{'s' if n_warn != 1 else ''}[/yellow]")
    if n_fail:
        summary_parts.append(f"[bright_red]{n_fail} failure{'s' if n_fail != 1 else ''}[/bright_red]")

    console.print(
        Panel(
            "  " + "  ·  ".join(summary_parts),
            title="[bold]◉ SUMMARY[/bold]",
            border_style="cyan" if n_fail == 0 else "bright_red",
            box=box.DOUBLE_EDGE,
            padding=(0, 1),
        )
    )
    console.print()

    failures = [k for k, v in results.items() if v["status"] == "fail"]
    if failures:
        fix_lines = []
        for check in failures:
            fix = _DOCTOR_FIXES.get(check)
            if check.startswith("tool:"):
                tool_name = check[5:]
                fix = f"ccm uninstall {tool_name} && ccm install {tool_name}"
            if fix:
                fix_lines.append(f"  [dim]{check.replace('tool:', '').replace('_', ' ')}:[/dim]  [bright_cyan]{fix}[/bright_cyan]")
        if fix_lines:
            console.print(
                Panel(
                    "\n".join(fix_lines),
                    title="[bold bright_red]◆ FIX SUGGESTIONS[/bold bright_red]",
                    border_style="bright_red",
                    box=box.SIMPLE_HEAVY,
                    padding=(0, 1),
                )
            )
            console.print()
        raise typer.Exit(1)
