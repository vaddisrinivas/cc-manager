"""cc-manager doctor command."""
from __future__ import annotations

import sys
import time
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]
from pathlib import Path

import typer
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.padding import Padding
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TaskProgressColumn
from rich.rule import Rule
from rich.text import Text

import cc_manager.context as ctx_mod
from cc_manager.context import get_ctx, run_cmd
from cc_manager.display import console

app = typer.Typer()


def run_checks() -> dict[str, dict]:
    """Run all doctor checks. Returns dict of check_name -> {status, message}."""
    ctx = get_ctx()
    results: dict[str, dict] = {}

    # Python version check
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 11):
        results["python_version"] = {"status": "ok", "message": f"Python {major}.{minor}"}
    else:
        results["python_version"] = {"status": "fail", "message": f"Python {major}.{minor} < 3.11"}

    # Config valid check
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

    # Store writable check
    store_path = ctx_mod.STORE_PATH
    try:
        store_path.parent.mkdir(parents=True, exist_ok=True)
        test_file = store_path.parent / ".write_test"
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink()
        results["store_writable"] = {"status": "ok", "message": str(store_path.parent)}
    except Exception as e:
        results["store_writable"] = {"status": "fail", "message": str(e)}

    # Hooks registered check
    settings = ctx.settings
    hooks = settings.get("hooks", {})
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

    # Installed tools checks
    for tool_name, info in ctx.installed.get("tools", {}).items():
        # Find detect command from registry
        reg_entry = next((t for t in ctx.registry if t["name"] == tool_name), None)
        if reg_entry is None:
            results[f"tool:{tool_name}"] = {"status": "warn", "message": "Not in registry"}
            continue

        detect = reg_entry.get("detect", {})
        cmd = detect.get("command", "")
        settings_key = detect.get("settings_json_key", "")

        if cmd:
            rc, output = run_cmd(cmd)
            if rc == 0:
                results[f"tool:{tool_name}"] = {"status": "ok", "message": output.strip()[:80]}
            else:
                results[f"tool:{tool_name}"] = {"status": "fail", "message": f"Not found: {cmd}"}
        elif settings_key:
            parts = settings_key.split(".")
            val = settings
            for part in parts:
                if isinstance(val, dict):
                    val = val.get(part)
                else:
                    val = None
                    break
            if val is not None:
                results[f"tool:{tool_name}"] = {"status": "ok", "message": f"Found in settings: {settings_key}"}
            else:
                results[f"tool:{tool_name}"] = {"status": "warn", "message": f"Not found in settings: {settings_key}"}
        else:
            results[f"tool:{tool_name}"] = {"status": "ok", "message": "Manual install (no detect)"}

    # Log doctor event
    ctx.store.append("doctor", results={k: v["status"] for k, v in results.items()})
    return results


def _status_icon(status: str) -> str:
    return {
        "ok": "[bright_green]  ✓[/bright_green]",
        "warn": "[yellow]  ⚠[/yellow]",
        "fail": "[bright_red]  ✗[/bright_red]",
    }.get(status, "  ?")


def _status_label(status: str) -> str:
    return {
        "ok": "[bright_green]ok[/bright_green]",
        "warn": "[yellow]warn[/yellow]",
        "fail": "[bright_red]FAIL[/bright_red]",
    }.get(status, status)


@app.command("doctor")
def doctor_cmd() -> None:
    """Run diagnostic checks on the cc-manager installation."""
    # ── Header ────────────────────────────────────────────────────────────────
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

    # ── Fake scanning progress ────────────────────────────────────────────────
    with Progress(
        SpinnerColumn("dots12", style="bright_cyan"),
        TextColumn("[bright_cyan]{task.description}[/bright_cyan]"),
        BarColumn(bar_width=22, style="cyan", complete_style="bright_cyan"),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        t1 = progress.add_task("Scanning configuration...", total=100)
        t2 = progress.add_task("Checking installed tools...", total=100)
        t3 = progress.add_task("Validating hooks...", total=100)
        for i in range(0, 101, 5):
            progress.update(t1, completed=i)
            time.sleep(0.01)
        for i in range(0, 101, 5):
            progress.update(t2, completed=i)
            time.sleep(0.01)
        for i in range(0, 101, 5):
            progress.update(t3, completed=i)
            time.sleep(0.01)

    # ── Run actual checks ─────────────────────────────────────────────────────
    results = run_checks()

    # ── Group results into categories ─────────────────────────────────────────
    system_checks = {k: v for k, v in results.items() if not k.startswith("tool:")}
    tool_checks = {k: v for k, v in results.items() if k.startswith("tool:")}

    def _render_check_rows(checks: dict) -> str:
        lines = []
        for check, info in checks.items():
            icon = _status_icon(info["status"])
            label = _status_label(info["status"])
            display_name = check.replace("tool:", "").replace("_", " ")
            msg = info.get("message", "")
            lines.append(f"{icon}  [bright_white]{display_name:<24}[/bright_white]  [dim]{msg[:56]}[/dim]")
        return "\n".join(lines) if lines else "  [dim]No checks[/dim]"

    # System panel
    console.print(
        Panel(
            _render_check_rows(system_checks),
            title="[bold bright_cyan]◆ SYSTEM[/bold bright_cyan]",
            border_style="cyan",
            box=box.SIMPLE_HEAVY,
            padding=(0, 1),
        )
    )

    # Tools panel
    if tool_checks:
        console.print(
            Panel(
                _render_check_rows(tool_checks),
                title="[bold bright_cyan]◆ EXTERNAL TOOLS[/bold bright_cyan]",
                border_style="cyan",
                box=box.SIMPLE_HEAVY,
                padding=(0, 1),
            )
        )

    # ── Summary ───────────────────────────────────────────────────────────────
    n_ok = sum(1 for v in results.values() if v["status"] == "ok")
    n_warn = sum(1 for v in results.values() if v["status"] == "warn")
    n_fail = sum(1 for v in results.values() if v["status"] == "fail")

    summary_parts = []
    summary_parts.append(f"[bright_green]{n_ok} passed[/bright_green]")
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

    has_fail = any(v["status"] == "fail" for v in results.values())
    if has_fail:
        raise typer.Exit(1)
