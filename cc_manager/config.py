"""cc-manager — all constants and defaults in one place."""
from __future__ import annotations
from pydantic import BaseModel

HOOK_EVENTS = ["Stop", "SessionStart", "SessionEnd", "PostToolUse", "PreCompact"]

MODULES = [
    ("later",   "dispatch deferred tasks at window end"),
    ("compact", "context recovery after compaction"),
    ("resume",  "auto-resume limit-hit tasks"),
    ("budget",  "global budget enforcement"),
    ("window",  "5-hour window lifecycle"),
    ("stats",   "token analytics + cost tracking"),
    ("nudge",   "stale agent detection"),
]


class Pricing(BaseModel):
    sonnet_input: float = 3.00
    sonnet_output: float = 15.00
    opus_input: float = 15.00
    opus_output: float = 75.00
    haiku_input: float = 0.25
    haiku_output: float = 1.25
    sonnet_cache_write: float = 3.75
    sonnet_cache_read: float = 0.30
    opus_cache_write: float = 18.75
    opus_cache_read: float = 1.50
    haiku_cache_write: float = 0.30
    haiku_cache_read: float = 0.03


class CCConfig(BaseModel):
    backup_on_change: bool = True
    log_level: str = "info"
    weekly_budget_tokens: int = 10_000_000
    backoff_at_pct: int = 80
    window_minutes: int = 300
    cost_tracking: bool = True
    pricing: Pricing = Pricing()

    def to_toml(self) -> str:
        p = self.pricing
        return (
            "[manager]\nschema_version = 1\n"
            f"backup_on_change = {str(self.backup_on_change).lower()}\n"
            f'log_level = "{self.log_level}"\n'
            "\n[later]\nenabled = true\n"
            "\n[compact]\nenabled = true\n"
            "\n[resume]\nenabled = true\n"
            "\n[budget]\nenabled = true\n"
            f"weekly_budget_tokens = {self.weekly_budget_tokens:_}\n"
            f"backoff_at_pct = {self.backoff_at_pct}\n"
            "\n[window]\nenabled = true\n"
            f"duration_minutes = {self.window_minutes}\n"
            "\n[stats]\nenabled = true\n"
            f"cost_tracking = {str(self.cost_tracking).lower()}\n"
            "\n[stats.pricing]\n"
            f"sonnet_input = {p.sonnet_input}\nsonnet_output = {p.sonnet_output}\n"
            f"opus_input = {p.opus_input}\nopus_output = {p.opus_output}\n"
            f"haiku_input = {p.haiku_input}\nhaiku_output = {p.haiku_output}\n"
            f"sonnet_cache_write = {p.sonnet_cache_write}\nsonnet_cache_read = {p.sonnet_cache_read}\n"
            f"opus_cache_write = {p.opus_cache_write}\nopus_cache_read = {p.opus_cache_read}\n"
            f"haiku_cache_write = {p.haiku_cache_write}\nhaiku_cache_read = {p.haiku_cache_read}\n"
            "\n[nudge]\nenabled = true\nstale_minutes = 10\nmax_retries = 2\n"
        )


# Module-level singletons
pricing = Pricing()
cfg = CCConfig()
