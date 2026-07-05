"""
Static $/token pricing table used to estimate cost per AI call.

Approximate public list prices; unknown (provider, model) pairs default to 0.0
rather than raising, so usage logging never breaks on a new/unlisted model.
"""

from __future__ import annotations

from decimal import Decimal

# (provider, model) -> (cost per 1K input tokens, cost per 1K output tokens), in USD.
_PRICING: dict[tuple[str, str], tuple[Decimal, Decimal]] = {
    ("gemini", "gemini-2.5-flash"): (Decimal("0.0003"), Decimal("0.0025")),
    ("gemini", "gemini-2.5-flash-lite"): (Decimal("0.0001"), Decimal("0.0004")),
    ("gemini", "gemini-2.5-pro"): (Decimal("0.00125"), Decimal("0.01")),
}


def estimate_cost_usd(
    provider: str, model: str, input_tokens: int | None, output_tokens: int | None
) -> Decimal:
    rates = _PRICING.get((provider, model))
    if rates is None:
        return Decimal("0")

    input_rate, output_rate = rates
    input_cost = (Decimal(input_tokens or 0) / 1000) * input_rate
    output_cost = (Decimal(output_tokens or 0) / 1000) * output_rate
    return input_cost + output_cost
