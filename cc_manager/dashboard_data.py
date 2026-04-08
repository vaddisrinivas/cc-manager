"""cc-manager dashboard data — pure data fetch, no UI."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict

from cc_manager import __version__
from cc_manager.context import get_ctx
from cc_manager.context import daily_buckets, run_health_checks
from cc_manager.commands.recommend import get_recommendations


class DashboardData(TypedDict):
    """Typed contract for the dict consumed by all dashboard widgets.

    Using TypedDict gives IDE auto-complete and catches key-name typos at
    type-check time instead of silently producing empty tables at runtime.
    """
    version: str
    timestamp: str
    status: str                                  # "NOMINAL" | "DEGRADED"
    sessions: list[dict]
    total_input: int
    total_output: int
    total_cost: float
    total_tokens: int
    avg_tokens_per_session: int
    model_breakdown: Any                         # Counter[str]
    spark_values: list[int]
    spark_days: list[str]
    daily_cost: dict[str, float]
    installed: dict[str, dict]
    health_checks: list[tuple[str, str, str]]    # (name, status, detail)
    cc_hooks: int
    settings_ok: bool
    recs: list[dict]
    available: list[dict]
    events: list[dict]


def build_data(period_days: int = 7) -> DashboardData:
    """Fetch all dashboard data. Returns a plain dict for widgets to consume."""
    ctx = get_ctx()
    since = datetime.now(timezone.utc) - timedelta(days=period_days)
    sessions = ctx.store.sessions(since=since)
    events = ctx.store.tail(20)

    total_input = sum(s.get("input_tokens", 0) for s in sessions)
    total_output = sum(s.get("output_tokens", 0) for s in sessions)
    total_cost = sum(s.get("cost_usd", 0.0) for s in sessions)
    total_tokens = total_input + total_output
    avg_tokens_per_session = total_tokens // max(len(sessions), 1)

    model_breakdown: Counter = Counter(s.get("model", "unknown") for s in sessions)

    daily, daily_cost = daily_buckets(sessions)
    sorted_days = sorted(daily.keys())
    spark_values = [daily[d] for d in sorted_days] if sorted_days else [0] * 7

    installed = ctx.installed.get("tools", {})
    checks = run_health_checks(installed, ctx.registry_map, ctx.settings)

    settings_ok = ctx.settings is not None
    hooks = ctx.settings.get("hooks", {})
    cc_hooks = sum(
        1 for entries in hooks.values()
        for entry in entries
        for h in entry.get("hooks", [])
        if ".cc-manager" in h.get("command", "")
    )

    all_ok = settings_ok and all(c[1] == "ok" for c in checks)
    status = "NOMINAL" if all_ok else "DEGRADED"
    now_str = datetime.now().strftime("%H:%M:%S")

    try:
        recs = get_recommendations(ctx)
    except Exception:
        recs = []

    installed_names = set(installed.keys())
    available = [
        t for t in ctx.registry
        if t.get("tier") == "recommended" and t["name"] not in installed_names
    ]

    return {
        "version": __version__,
        "timestamp": now_str,
        "status": status,
        "sessions": sessions,
        "total_input": total_input,
        "total_output": total_output,
        "total_cost": total_cost,
        "total_tokens": total_tokens,
        "avg_tokens_per_session": avg_tokens_per_session,
        "model_breakdown": model_breakdown,
        "spark_values": spark_values,
        "spark_days": sorted_days,
        "daily_cost": dict(daily_cost),
        "installed": installed,
        "health_checks": checks,
        "cc_hooks": cc_hooks,
        "settings_ok": settings_ok,
        "recs": recs,
        "available": available,
        "events": events,
    }
