"""SessionEnd handler."""
from __future__ import annotations
EVENT = "SessionEnd"
TIMEOUT_MS = 10000

def _get_model_pricing(config: dict, model: str) -> tuple[float, float, float]:
    """Return (input_per_m, output_per_m, cache_read_per_m) in USD."""
    pricing = config.get("stats", {}).get("pricing", {})
    model_lower = model.lower() if model else ""
    if "opus" in model_lower:
        return pricing.get("opus_input", 15.0), pricing.get("opus_output", 75.0), pricing.get("opus_cache_read", 1.50)
    elif "haiku" in model_lower:
        return pricing.get("haiku_input", 0.25), pricing.get("haiku_output", 1.25), pricing.get("haiku_cache_read", 0.03)
    else:  # sonnet default
        return pricing.get("sonnet_input", 3.0), pricing.get("sonnet_output", 15.0), pricing.get("sonnet_cache_read", 0.30)

def handle(payload: dict, ctx) -> dict:
    session_id = payload.get("session_id", payload.get("sessionId", "unknown"))
    usage = payload.get("usage", {})
    input_tokens = usage.get("input_tokens", payload.get("input_tokens", 0))
    output_tokens = usage.get("output_tokens", payload.get("output_tokens", 0))
    cache_read = usage.get("cache_read_input_tokens", payload.get("cache_read", 0))
    model = payload.get("model", "sonnet")

    inp_rate, out_rate, cache_rate = _get_model_pricing(ctx.config, model)
    cost = (input_tokens * inp_rate + output_tokens * out_rate + cache_read * cache_rate) / 1_000_000

    duration_min = payload.get("duration_min", 0)
    ctx.store.append(
        "session_end",
        session=session_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read=cache_read,
        cost_usd=round(cost, 6),
        duration_min=duration_min,
        model=model,
    )
    return {}
