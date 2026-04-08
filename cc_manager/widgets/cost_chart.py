"""Cost breakdown by model widget."""
from __future__ import annotations
from collections import Counter
from textual.widget import Widget
from textual.widgets import Static
from cc_manager.commands.tui import sparkline
from cc_manager.context import fmt_tokens as abbrev


class CostChart(Widget):
    """Cost breakdown panel: model bar chart + daily cost sparkline."""
    DEFAULT_CSS = """
    CostChart {
        height: 14;
        border: solid $accent;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._content = Static("Loading...")

    def compose(self):
        yield self._content

    def update(self, data: dict) -> None:
        model_counts: Counter = data.get("model_breakdown", Counter())
        total_cost = data.get("total_cost", 0.0)
        total_sessions = max(sum(model_counts.values()), 1)
        daily_cost: dict = data.get("daily_cost", {})

        lines = ["[dim]cost breakdown · 7d[/dim]", ""]

        if not model_counts:
            empty_spark = sparkline([], width=42)
            lines.append(f"  [dim]{empty_spark}[/dim]")
            lines.append("")
            lines.append("  [dim]no sessions yet[/dim]")
        else:
            # Model breakdown bars
            for model, count in model_counts.most_common(5):
                pct = count / total_sessions
                bar_filled = int(pct * 22)
                filled = "█" * bar_filled
                bar = (f"[magenta]{filled}[/magenta]" if filled else "") + "[dim]░[/dim]" * (22 - bar_filled)
                model_cost = total_cost * pct
                short = model.replace("claude-", "").replace("-latest", "")[:14]
                lines.append(
                    f"  [cyan]{short:<16}[/cyan]{bar}  "
                    f"[dim]{pct*100:.0f}%[/dim]  [green]${model_cost:.4f}[/green]"
                )

            lines.append("")
            lines.append(f"  [dim]Total cost (7d):[/dim] [bright_green]${total_cost:.4f}[/bright_green]")
            lines.append("")

            # Daily cost sparkline
            if daily_cost:
                sorted_days = sorted(daily_cost.keys())[-7:]
                day_vals = [daily_cost.get(d, 0.0) * 1000 for d in sorted_days]  # scale to milli$
                day_spark = sparkline([int(v) for v in day_vals], width=42)
                lines.append("  [dim]Daily cost trend:[/dim]")
                lines.append(f"  [green]{day_spark}[/green]")

        self._content.update("\n".join(lines))
