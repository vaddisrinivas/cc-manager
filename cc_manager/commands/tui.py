"""cc-manager TUI command — full-screen Textual dashboard."""
from __future__ import annotations

import typer

from cc_manager.context import fmt_tokens
from cc_manager.commands.recommend import get_recommendations

# Backwards-compat aliases (imported by widgets and tests)
abbrev = fmt_tokens

app = typer.Typer()

_BLOCK_CHARS = " ▁▂▃▄▅▆▇█"


def sparkline(values: list, width: int = 24) -> str:
    """ASCII sparkline from a list of numeric values."""
    if not values:
        return "─" * width
    max_v = max(values) or 1
    step = len(values) / width
    return "".join(
        _BLOCK_CHARS[int((values[min(int(i * step), len(values) - 1)] / max_v) * 8)]
        for i in range(width)
    )


@app.command("tui")
def run(
    live: bool = typer.Option(False, "--live", "-l", hidden=True),
    refresh: int = typer.Option(30, "--refresh", "-r", hidden=True),
    interactive: bool = typer.Option(False, "--interactive", "-i", hidden=True),
) -> None:
    """Full-screen terminal dashboard. Press Q to quit, R to refresh."""
    from cc_manager.app import CCManagerApp
    CCManagerApp().run()
