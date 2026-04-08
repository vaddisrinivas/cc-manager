"""Token usage sparkline widget."""
from __future__ import annotations
from textual.widget import Widget
from textual.widgets import Static
from cc_manager.commands.tui import sparkline
from cc_manager.context import fmt_tokens as abbrev

BLOCK_CHARS = " ▁▂▃▄▅▆▇█"


class TokenChart(Widget):
    """Sparkline token usage chart panel."""
    DEFAULT_CSS = """
    TokenChart {
        height: 14;
        border: solid $primary;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._content = Static("Loading...")

    def compose(self):
        yield self._content

    def update(self, data: dict) -> None:
        spark_values = data.get("spark_values", [])
        spark_days = data.get("spark_days", [])
        total = data.get("total_tokens", 0)
        inp = data.get("total_input", 0)
        out = data.get("total_output", 0)
        avg = data.get("avg_tokens_per_session", 0)
        sessions = data.get("sessions", [])

        # Wide sparkline filling the panel
        spark = sparkline(spark_values, width=42)

        lines = ["[dim]token usage · 7d[/dim]", ""]

        if not sessions:
            lines.append(f"  [dim]{spark}[/dim]")
            lines.append("")
            lines.append("  [dim]no sessions yet[/dim]")
        else:
            lines.append(f"  [cyan]{spark}[/cyan]")
            lines.append("")
            lines.append(
                f"  [dim]Total:[/dim]  [bright_white]{abbrev(total)}[/bright_white] tokens   "
                f"[dim]In:[/dim] [bright_white]{abbrev(inp)}[/bright_white]   "
                f"[dim]Out:[/dim] [bright_white]{abbrev(out)}[/bright_white]"
            )
            lines.append(
                f"  [dim]Sessions:[/dim] [bright_white]{len(sessions)}[/bright_white]   "
                f"[dim]Avg/session:[/dim] [bright_white]{abbrev(avg)}[/bright_white] tokens"
            )
            lines.append("")

            # Per-day breakdown (last 5 days)
            if spark_days and spark_values:
                lines.append("  [dim]Daily breakdown:[/dim]")
                pairs = list(zip(spark_days, spark_values))[-5:]
                for day, val in pairs:
                    bar_w = min(int(val / max(max(spark_values), 1) * 18), 18)
                    filled = "▮" * bar_w
                    bar = (f"[cyan]{filled}[/cyan]" if filled else "") + "[dim]·[/dim]" * (18 - bar_w)
                    lines.append(f"  [dim]{day[-5:]}[/dim]  {bar}  [bright_white]{abbrev(val)}[/bright_white]")

        self._content.update("\n".join(lines))
