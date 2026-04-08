"""cc-manager theme — shared markup constants and formatters."""
from __future__ import annotations

# ── Status labels (Rich markup) ───────────────────────────────────────────────

_STATUS_LABELS: dict[str, str] = {
    "ok":   "[bright_green]✓ ok[/bright_green]",
    "warn": "[yellow]⚠ warn[/yellow]",
    "fail": "[bright_red]✗ fail[/bright_red]",
}

_STATUS_ICONS: dict[str, str] = {
    "ok":   "[bright_green]  ✓[/bright_green]",
    "warn": "[yellow]  ⚠[/yellow]",
    "fail": "[bright_red]  ✗[/bright_red]",
}

_STATUS_WORDS: dict[str, str] = {
    "ok":   "[bright_green]ok[/bright_green]",
    "warn": "[yellow]warn[/yellow]",
    "fail": "[bright_red]FAIL[/bright_red]",
}

_TIER_LABELS: dict[str, str] = {
    "recommended": "[bright_cyan]★ recommended[/bright_cyan]",
    "popular":     "[bright_green]◆ popular[/bright_green]",
    "community":   "[dim]· community[/dim]",
}


def status_label(status: str) -> str:
    """Return Rich markup label for a status string (ok/warn/fail)."""
    return _STATUS_LABELS.get(status, f"[dim]{status}[/dim]")


def status_icon(status: str) -> str:
    """Return Rich markup icon prefix for a status string."""
    return _STATUS_ICONS.get(status, "  ?")


def status_word(status: str) -> str:
    """Return coloured status word (used in doctor summary rows)."""
    return _STATUS_WORDS.get(status, status)


def tier_label(tier: str) -> str:
    """Return Rich markup label for a tool tier string."""
    return _TIER_LABELS.get(tier, f"[dim]{tier}[/dim]")


def health_dot(ok: bool, warn: bool = False) -> str:
    """Filled dot coloured by health state — for compact status displays."""
    if ok:
        return "[bright_green]●[/bright_green]"
    if warn:
        return "[yellow]◐[/yellow]"
    return "[bright_red]●[/bright_red]"
