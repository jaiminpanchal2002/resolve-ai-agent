"""Per-model LLM pricing (USD per 1M tokens) and cost estimation.

Prices are approximations for cost *estimation* and observability,
not billing. Update this table when providers change pricing.
"""

from decimal import Decimal

# model_name -> (input_usd_per_1m_tokens, output_usd_per_1m_tokens)
MODEL_PRICING: dict[str, tuple[Decimal, Decimal]] = {
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    "gpt-4o": (Decimal("2.50"), Decimal("10.00")),
    "gpt-4.1-mini": (Decimal("0.40"), Decimal("1.60")),
    "gemini-1.5-flash": (Decimal("0.075"), Decimal("0.30")),
    "gemini-2.0-flash": (Decimal("0.10"), Decimal("0.40")),
    "gemini-2.5-flash": (Decimal("0.075"), Decimal("0.30")),
    "gemini-3.5-flash": (Decimal("0.075"), Decimal("0.30")),
    "mock-model": (Decimal("0.0"), Decimal("0.0")),
}

_DEFAULT_PRICING = (Decimal("1.00"), Decimal("3.00"))  # conservative fallback


def estimate_cost(model_name: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Estimate USD cost of a call from token counts for a given model."""
    input_price, output_price = MODEL_PRICING.get(model_name, _DEFAULT_PRICING)
    per_token = Decimal("0.000001")
    return (
        Decimal(input_tokens) * input_price * per_token
        + Decimal(output_tokens) * output_price * per_token
    )
