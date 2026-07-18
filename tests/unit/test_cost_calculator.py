from decimal import Decimal

from resolveai.core.pricing import MODEL_PRICING, estimate_cost


def test_cost_calculation_gpt4o_mini():
    # 2000 input ($0.00030) + 500 output ($0.00030) = $0.00060
    assert estimate_cost("gpt-4o-mini", 2000, 500) == Decimal("0.000600")


def test_cost_zero_tokens():
    assert estimate_cost("gpt-4o-mini", 0, 0) == Decimal("0.0")


def test_cost_large_usage():
    # 100k in + 20k out on gpt-4o-mini = 0.015 + 0.012 = 0.027
    assert estimate_cost("gpt-4o-mini", 100_000, 20_000) == Decimal("0.027000")


def test_cost_per_model_differs():
    cheap = estimate_cost("gemini-1.5-flash", 10_000, 2_000)
    expensive = estimate_cost("gpt-4o", 10_000, 2_000)
    assert expensive > cheap


def test_unknown_model_uses_conservative_fallback():
    cost = estimate_cost("some-future-model", 1_000_000, 0)
    assert cost > Decimal("0")
    assert "some-future-model" not in MODEL_PRICING


def test_fake_provider_costs_nothing():
    assert estimate_cost("mock-model", 1_000_000, 1_000_000) == Decimal("0.0")
