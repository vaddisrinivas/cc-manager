"""cc-manager TUI command — full-screen terminal dashboard mirroring the web dashboard."""
from __future__ import annotations

import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import typer
from rich import box
from rich.columns import Columns
from rich.console import Console, Group
from rich.live import Live
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from cc_manager import __version__
from cc_manager.context import get_ctx
from cc_manager.display import console

app = typer.Typer()

# ── Helpers ────────────────────────────────────────────────────────────────────

BLOCK_CHARS = " ▁▂▃▄▅▆▇█"


def sparkline(values: list, width: int = 24) -> str:
    """Generate an ASCII sparkline from a list of numeric values."""
    if not values:
        return "─" * width
    max_v = max(values) or 1
    step = len(values) / width
    return "".join(
        BLOCK_CHARS[int((values[min(int(i * step), len(values) - 1)] / max_v) * 8)]
        for i in range(width)
    )


def abbrev(n: int) -> str:
    """Abbreviate large numbers (1_500_000 → '1.5M', 450_000 → '450K')."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def get_recommendations(ctx) -> list[dict]:
    """Return recommendation dicts without printing anything.

    Each dict has keys: tool (str|None), message (str), install_cmd (str|None).
    """
    from cc_manager.commands.analyze import compute_stats

    stats = compute_stats(period_days=7)
    installed = set(ctx.installed.get("tools", {}).keys())
    recs: list[dict] = []

    if "rtk" not in installed:
        avg_tokens = stats.get("avg_tokens_per_session", 0)
        if avg_tokens > 500_000:
            recs.append({
                "tool": "rtk",
                "message": f"avg session tokens={avg_tokens:,} > 500K — token filter can save 60-90%",
                "install_cmd": "ccm install rtk",
            })

    if stats.get("compaction_count", 0) > 2 * max(stats.get("sessions", 1), 1):
        if "rtk" not in installed:
            recs.append({
                "tool": "rtk",
                "message": "High compaction frequency detected",
                "install_cmd": "ccm install rtk",
            })

    mcp_servers = ctx.settings.get("mcpServers", {})
    if not mcp_servers:
        if "context7" not in installed:
            recs.append({
                "tool": "context7",
                "message": "No MCP servers configured — context7 gives version-specific docs",
                "install_cmd": "ccm install context7",
            })
        if "playwright-mcp" not in installed:
            recs.append({
                "tool": "playwright-mcp",
                "message": "No browser automation MCP configured",
                "install_cmd": "ccm install playwright-mcp",
            })

    security_tools = [
        t for t in installed
        if "security" in (
            next((x.get("category", "") for x in ctx.registry if x["name"] == t), "")
        )
    ]
    if not security_tools and "trail-of-bits" not in installed:
        recs.append({
            "tool": "trail-of-bits",
            "message": "No security tool installed",
            "install_cmd": "ccm install trail-of-bits",
        })

    opus_count = stats.get("model_breakdown", {}).get("opus", 0)
    total_sessions = stats.get("sessions", 0)
    if total_sessions > 0 and opus_count / total_sessions > 0.5:
        recs.append({
            "tool": None,
            "message": "Opus >50% of sessions — consider sonnet for cost savings",
            "install_cmd": None,
        })

    if "claude-squad" not in installed:
        recs.append({
            "tool": "claude-squad",
            "message": "No multi-agent orchestration tool installed",
            "install_cmd": "ccm install claude-squad",
        })

    return recs


# ── Dashboard builder ──────────────────────────────────────────────────────────

def build_dashboard():
    """Build the full dashboard as a Rich renderable Group."""
    ctx = get_ctx()

    # ── Data fetching ──────────────────────────────────────────────────────────
    since = datetime.now(timezone.utc) - timedelta(days=7)
    sessions = ctx.store.sessions(since=since)

    total_input = sum(s.get("input_tokens", 0) for s in sessions)
    total_output = sum(s.get("output_tokens", 0) for s in sessions)
    total_cost = sum(s.get("cost_usd", 0.0) for s in sessions)
    total_tokens = total_input + total_output
    avg_tokens_per_session = total_tokens // max(len(sessions), 1)

    # Model breakdown by session count
    model_counts: Counter = Counter(s.get("model", "unknown") for s in sessions)
    total_model_sessions = max(sum(model_counts.values()), 1)

    # Daily token buckets for sparkline
    daily: dict[str, int] = defaultdict(int)
    daily_cost: dict[str, float] = defaultdict(float)
    for s in sessions:
        day = (s.get("ts") or "")[:10]
        if day:
            daily[day] += s.get("input_tokens", 0) + s.get("output_tokens", 0)
            daily_cost[day] += s.get("cost_usd", 0.0)

    sorted_days = sorted(daily.keys())
    spark_values = [daily[d] for d in sorted_days] if sorted_days else [0] * 7
    spark = sparkline(spark_values, width=28)

    # Installed tools
    installed = ctx.installed.get("tools", {})

    # Quick health checks from registry detect commands
    checks: list[tuple[str, str, str]] = []
    from cc_manager.context import run_cmd
    for name, meta in installed.items():
        reg_entry = next((t for t in ctx.registry if t.get("name") == name), None)
        if reg_entry is None:
            checks.append((name, "warn", "not in registry"))
            continue
        detect = reg_entry.get("detect", {})
        detect_type = detect.get("type", "none")
        if detect_type == "binary":
            cmd = detect.get("command", "")
            rc, out = run_cmd(cmd, timeout=3)
            checks.append((name, "ok" if rc == 0 else "fail", out.strip()[:40]))
        elif detect_type == "settings_json_key":
            key = detect.get("key", "")
            parts = key.split(".")
            val = ctx.settings
            for part in parts:
                if isinstance(val, dict):
                    val = val.get(part)
                else:
                    val = None
                    break
            checks.append((name, "ok" if val is not None else "warn", key[:40]))
        else:
            checks.append((name, "ok", "configured"))

    # Also add core system checks
    settings_ok = (ctx.settings is not None)
    checks_for_header = checks + [
        ("settings.json", "ok" if settings_ok else "fail", ""),
    ]
    all_ok = all(c[1] == "ok" for c in checks_for_header)

    # Recommendations
    try:
        recs = get_recommendations(ctx)
    except Exception:
        recs = []

    # Available tools (recommended tier, not yet installed)
    installed_names = set(installed.keys())
    available = [
        t for t in ctx.registry
        if t.get("tier") == "recommended" and t["name"] not in installed_names
    ]

    # ── Panel: Header ──────────────────────────────────────────────────────────
    status_color = "bright_green" if all_ok else "yellow"
    status_text = "NOMINAL" if all_ok else "DEGRADED"
    now_str = datetime.now().strftime("%H:%M:%S")
    header = Rule(
        f"[bold bright_cyan]◉ CC-MANAGER[/bold bright_cyan]  "
        f"[dim]v{__version__}  ·  Claude Code Ecosystem Controller[/dim]  "
        f"[{status_color}]● {status_text}[/{status_color}]  "
        f"[dim]{now_str}[/dim]",
        style="bright_cyan",
    )

    # ── Panel: Token Usage sparkline ───────────────────────────────────────────
    token_content = (
        f"[bright_cyan]{spark}[/bright_cyan]\n"
        f"[dim]Total 7d:[/dim] [bright_white]{abbrev(total_tokens)}[/bright_white] tokens  "
        f"[dim]·  In:[/dim] [bright_white]{abbrev(total_input)}[/bright_white]  "
        f"[dim]Out:[/dim] [bright_white]{abbrev(total_output)}[/bright_white]\n"
        f"[dim]Avg/session:[/dim] [bright_white]{abbrev(avg_tokens_per_session)}[/bright_white]  "
        f"[dim]Sessions:[/dim] [bright_white]{len(sessions)}[/bright_white]"
    )
    token_panel = Panel(
        token_content,
        title="[dim]⚡ TOKEN USAGE (7d)[/dim]",
        border_style="cyan",
        box=box.SIMPLE_HEAVY,
        padding=(0, 1),
    )

    # ── Panel: Cost breakdown bar chart ───────────────────────────────────────
    cost_lines: list[str] = []
    for model, count in model_counts.most_common(6):
        pct = count / total_model_sessions
        bar_filled = int(pct * 22)
        bar = "[bright_cyan]" + "█" * bar_filled + "[/bright_cyan]" + "[dim]░[/dim]" * (22 - bar_filled)
        model_cost = total_cost * pct
        short_model = model.replace("claude-", "").replace("-latest", "")[:12]
        cost_lines.append(
            f"  [bright_cyan]{short_model:<14}[/bright_cyan]{bar}  "
            f"[dim]{pct * 100:.0f}%[/dim]  [bright_green]${model_cost:.2f}[/bright_green]"
        )
    if not cost_lines:
        cost_lines = ["  [dim]No session data[/dim]"]
    cost_lines.append(f"\n  [dim]Total cost (7d):[/dim] [bright_green]${total_cost:.4f}[/bright_green]")
    cost_panel = Panel(
        "\n".join(cost_lines),
        title="[dim]⚡ COST BREAKDOWN (7d)[/dim]",
        border_style="magenta",
        box=box.SIMPLE_HEAVY,
        padding=(0, 1),
    )

    # ── Panel: Installed Tools table ───────────────────────────────────────────
    tools_table = Table(
        box=box.SIMPLE_HEAVY,
        show_edge=True,
        border_style="cyan",
        expand=True,
        padding=(0, 1),
    )
    tools_table.add_column("TOOL", style="bright_cyan", no_wrap=True, min_width=12)
    tools_table.add_column("VERSION", style="bright_white", min_width=8)
    tools_table.add_column("METHOD", style="dim", min_width=6)
    tools_table.add_column("STATUS", min_width=10)

    for name, meta in installed.items():
        chk = next((c for c in checks if c[0] == name), None)
        if chk:
            status_str = (
                "[bright_green]✓ ok[/bright_green]"
                if chk[1] == "ok"
                else "[bright_red]✗ fail[/bright_red]"
                if chk[1] == "fail"
                else "[yellow]⚠ warn[/yellow]"
            )
        else:
            status_str = "[dim]--[/dim]"
        tools_table.add_row(
            f"✓ {name}",
            meta.get("version", "--"),
            meta.get("method", "--"),
            status_str,
        )
    if not installed:
        tools_table.add_row("[dim]No tools installed[/dim]", "", "", "")

    tools_panel = Panel(
        tools_table,
        title="[dim]⚡ INSTALLED TOOLS[/dim]  [dim]([R]emove tool)[/dim]",
        border_style="cyan",
        box=box.SIMPLE_HEAVY,
    )

    # ── Panel: Health ──────────────────────────────────────────────────────────
    health_table = Table(
        box=box.SIMPLE_HEAVY,
        show_edge=True,
        border_style="green",
        expand=True,
        padding=(0, 1),
    )
    health_table.add_column("CHECK", style="bright_white", min_width=16)
    health_table.add_column("STATUS", min_width=10)
    health_table.add_column("DETAIL", style="dim")

    # Core system checks
    hooks = ctx.settings.get("hooks", {})
    cc_hooks = sum(
        1
        for entries in hooks.values()
        for entry in entries
        for h in entry.get("hooks", [])
        if ".cc-manager" in h.get("command", "")
    )
    health_table.add_row(
        "settings.json",
        "[bright_green]✓ ok[/bright_green]" if settings_ok else "[bright_red]✗ fail[/bright_red]",
        "loaded",
    )
    health_table.add_row(
        "hooks",
        "[bright_green]✓ ok[/bright_green]" if cc_hooks >= 2 else "[yellow]⚠ warn[/yellow]" if cc_hooks > 0 else "[bright_red]✗ fail[/bright_red]",
        f"{cc_hooks} registered",
    )
    for name, status, detail in checks:
        icon = (
            "[bright_green]✓ ok[/bright_green]"
            if status == "ok"
            else "[bright_red]✗ fail[/bright_red]"
            if status == "fail"
            else "[yellow]⚠ warn[/yellow]"
        )
        health_table.add_row(name, icon, detail[:36] if detail else "")

    if not checks:
        health_table.add_row("[dim]No tools to check[/dim]", "", "")

    health_panel = Panel(
        health_table,
        title="[dim]⚡ HEALTH[/dim]  [dim]([D]octor)[/dim]",
        border_style="green",
        box=box.SIMPLE_HEAVY,
    )

    # ── Panel: Recent Sessions table ───────────────────────────────────────────
    sess_table = Table(
        box=box.SIMPLE_HEAVY,
        show_edge=True,
        border_style="cyan",
        expand=True,
        padding=(0, 1),
    )
    sess_table.add_column("TIME", style="dim", no_wrap=True, min_width=16)
    sess_table.add_column("MODEL", style="bright_cyan", min_width=14)
    sess_table.add_column("DUR", style="bright_white", min_width=5)
    sess_table.add_column("TOKENS", style="bright_white", min_width=7)
    sess_table.add_column("COST", style="bright_green", min_width=7)

    display_sessions = sessions[-8:] if sessions else []
    for s in reversed(display_sessions):
        ts_raw = s.get("ts", "")[:16].replace("T", " ")
        model_short = s.get("model", "--").replace("claude-", "").replace("-latest", "")
        dur_val = s.get("duration_min")
        dur_str = f"{dur_val}m" if dur_val is not None else "--"
        tok_total = s.get("input_tokens", 0) + s.get("output_tokens", 0)
        cost_val = s.get("cost_usd", 0.0)
        sess_table.add_row(
            ts_raw,
            model_short[:14],
            dur_str,
            abbrev(tok_total),
            f"${cost_val:.3f}",
        )
    if not display_sessions:
        sess_table.add_row("[dim]No sessions recorded[/dim]", "", "", "", "")

    sessions_panel = Panel(
        sess_table,
        title="[dim]⚡ RECENT SESSIONS (7d)[/dim]",
        border_style="cyan",
        box=box.SIMPLE_HEAVY,
    )

    # ── Panel: Recommendations ─────────────────────────────────────────────────
    if recs:
        rec_lines: list[str] = []
        for r in recs[:4]:
            rec_lines.append(f"  [bright_yellow]◆[/bright_yellow] {r.get('message', '')}")
            install_cmd = r.get("install_cmd")
            if install_cmd:
                rec_lines.append(f"    [bright_cyan]▶ {install_cmd}[/bright_cyan]")
            rec_lines.append("")
        rec_content = "\n".join(rec_lines).rstrip()
    else:
        rec_content = "  [bright_green]✦ All clear — setup looks optimal![/bright_green]"

    rec_panel = Panel(
        rec_content,
        title="[dim]⚡ RECOMMENDATIONS[/dim]",
        border_style="yellow",
        box=box.SIMPLE_HEAVY,
    )

    # ── Panel: Available Tools (registry) ─────────────────────────────────────
    if available:
        avail_table = Table(
            box=box.SIMPLE_HEAVY,
            show_edge=True,
            border_style="magenta",
            expand=True,
            padding=(0, 1),
        )
        avail_table.add_column("TOOL", style="bright_cyan", no_wrap=True, min_width=14)
        avail_table.add_column("CATEGORY", style="dim", min_width=14)
        avail_table.add_column("DESCRIPTION", style="dim")
        avail_table.add_column("INSTALL", style="bright_white", min_width=20)

        for t in available[:8]:
            desc = (t.get("description") or "")[:44]
            avail_table.add_row(
                t["name"],
                t.get("category", ""),
                desc,
                f"ccm install {t['name']}",
            )
        avail_panel = Panel(
            avail_table,
            title=f"[dim]⚡ AVAILABLE TOOLS[/dim]  [dim]({len(available)} recommended)[/dim]  [dim]([I]nstall)[/dim]",
            border_style="magenta",
            box=box.SIMPLE_HEAVY,
        )
    else:
        avail_panel = Panel(
            "[bright_green]  ✦ All recommended tools are installed![/bright_green]",
            title="[dim]⚡ AVAILABLE TOOLS[/dim]",
            border_style="magenta",
            box=box.SIMPLE_HEAVY,
        )

    # ── Footer ─────────────────────────────────────────────────────────────────
    footer = Rule(
        "[dim][Q]uit  [R]efresh  [I]nstall  [R]emove  [D]octor  [M]odule toggle  "
        "· Use --interactive for action prompt[/dim]",
        style="dim",
    )

    return Group(
        header,
        Padding("", (0, 0)),
        Columns([token_panel, cost_panel], equal=True, expand=True),
        Columns([tools_panel, health_panel], equal=True, expand=True),
        sessions_panel,
        rec_panel,
        avail_panel,
        footer,
    )


# ── Interactive loop ───────────────────────────────────────────────────────────

def _interactive_loop() -> None:
    """Interactive TUI with keyboard action prompt."""
    while True:
        console.clear()
        console.print(build_dashboard())
        console.print()

        try:
            action = typer.prompt(
                "Action (i <tool> / r <tool> / d / m <module> on|off / q)",
                default="q",
            ).strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if not action or action == "q":
            break

        elif action == "d":
            console.print()
            from cc_manager.commands.doctor import run_checks
            results = run_checks()
            n_ok = sum(1 for v in results.values() if v["status"] == "ok")
            n_fail = sum(1 for v in results.values() if v["status"] == "fail")
            n_warn = sum(1 for v in results.values() if v["status"] == "warn")
            console.print(
                Panel(
                    f"  [bright_green]{n_ok} passed[/bright_green]  "
                    f"[yellow]{n_warn} warnings[/yellow]  "
                    f"[bright_red]{n_fail} failed[/bright_red]",
                    title="[bold bright_cyan]◉ DOCTOR RESULTS[/bold bright_cyan]",
                    border_style="cyan",
                    box=box.SIMPLE_HEAVY,
                )
            )
            input("Press Enter to continue...")

        elif action.startswith("i "):
            tool = action[2:].strip()
            if not tool:
                console.print("[yellow]Usage: i <tool-name>[/yellow]")
                input("Press Enter to continue...")
                continue
            console.print(f"\n[bright_cyan]Installing {tool}...[/bright_cyan]")
            try:
                from cc_manager.commands.install import install_tool
                install_tool(tool)
                console.print(f"[bright_green]✓ {tool} installed[/bright_green]")
            except Exception as e:
                console.print(f"[bright_red]✗ Error: {e}[/bright_red]")
            # Reset ctx so next render picks up new install state
            import cc_manager.context as ctx_mod
            ctx_mod._ctx = None
            input("Press Enter to continue...")

        elif action.startswith("r "):
            tool = action[2:].strip()
            if not tool:
                console.print("[yellow]Usage: r <tool-name>[/yellow]")
                input("Press Enter to continue...")
                continue
            if typer.confirm(f"Remove {tool}?", default=False):
                console.print(f"\n[bright_cyan]Removing {tool}...[/bright_cyan]")
                try:
                    from cc_manager.commands.uninstall import uninstall_cmd
                    # Uninstall cmd expects a typer invocation; call underlying logic directly
                    ctx = get_ctx()
                    installed = ctx.installed.get("tools", {})
                    if tool not in installed:
                        console.print(f"[yellow]⚠ {tool} is not installed[/yellow]")
                    else:
                        import json
                        installed.pop(tool, None)
                        import cc_manager.context as ctx_mod
                        ctx_mod.REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
                        ctx_mod.REGISTRY_PATH.write_text(
                            json.dumps(ctx.installed, indent=2), encoding="utf-8"
                        )
                        ctx.store.append("uninstall", tool=tool)
                        console.print(f"[bright_green]✓ {tool} removed[/bright_green]")
                        ctx_mod._ctx = None
                except Exception as e:
                    console.print(f"[bright_red]✗ Error: {e}[/bright_red]")
            input("Press Enter to continue...")

        elif action.startswith("m "):
            parts = action.split()
            if len(parts) == 3:
                module_name, state = parts[1], parts[2]
                enabled = state in ("on", "true", "1", "yes")
                ctx = get_ctx()
                if module_name in ctx.config:
                    ctx.config[module_name]["enabled"] = enabled
                    try:
                        import cc_manager.context as ctx_mod
                        import tomllib
                        # Write config back using toml format (basic)
                        _write_toml(ctx.config, ctx_mod.CONFIG_PATH)
                        console.print(
                            f"[bright_green]✓ Module {module_name} "
                            f"{'enabled' if enabled else 'disabled'}[/bright_green]"
                        )
                    except Exception as e:
                        console.print(f"[yellow]⚠ Could not save config: {e}[/yellow]")
                else:
                    console.print(f"[yellow]⚠ Module '{module_name}' not found in config[/yellow]")
            else:
                console.print("[yellow]Usage: m <module> on|off[/yellow]")
            input("Press Enter to continue...")

        else:
            console.print(f"[yellow]Unknown action: {action!r}[/yellow]")
            input("Press Enter to continue...")


def _write_toml(config: dict, path) -> None:
    """Minimal TOML writer for simple flat/nested dicts (config save)."""
    import pathlib

    lines: list[str] = []
    for section, value in config.items():
        if isinstance(value, dict):
            lines.append(f"[{section}]")
            for k, v in value.items():
                if isinstance(v, bool):
                    lines.append(f"{k} = {'true' if v else 'false'}")
                elif isinstance(v, str):
                    lines.append(f'{k} = "{v}"')
                else:
                    lines.append(f"{k} = {v}")
            lines.append("")
        else:
            if isinstance(value, bool):
                lines.append(f"{section} = {'true' if value else 'false'}")
            elif isinstance(value, str):
                lines.append(f'{section} = "{value}"')
            else:
                lines.append(f"{section} = {value}")

    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(path).write_text("\n".join(lines), encoding="utf-8")


# ── Command entry point ────────────────────────────────────────────────────────

@app.command("tui")
def run(
    live: bool = typer.Option(False, "--live", "-l", help="Auto-refresh every N seconds"),
    refresh: int = typer.Option(30, "--refresh", "-r", help="Refresh interval in seconds (with --live)"),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Enable interactive action prompt"
    ),
) -> None:
    """Full-screen terminal dashboard — mirrors the web dashboard 1:1.

    Examples:
      ccm tui                      # Render once (static)
      ccm tui --live               # Auto-refresh every 30s, Ctrl+C to exit
      ccm tui --live --refresh 10  # Auto-refresh every 10s
      ccm tui --interactive        # Show action prompt after rendering
    """
    if live:
        with Live(
            build_dashboard(),
            console=console,
            refresh_per_second=0.1,
            screen=True,
        ) as live_display:
            try:
                while True:
                    time.sleep(refresh)
                    live_display.update(build_dashboard())
            except KeyboardInterrupt:
                pass
    elif interactive:
        _interactive_loop()
    else:
        console.print(build_dashboard())
