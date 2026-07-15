from decimal import Decimal
import pytest

def calculate_cost(input_tokens: int, output_tokens: int) -> Decimal:
    """Calculates LLM run cost based on GPT-4o-mini rates."""
    # $0.15 per 1M input tokens, $0.60 per 1M output tokens
    input_rate = Decimal("0.00000015")
    output_rate = Decimal("0.00000060")
    return Decimal(input_tokens) * input_rate + Decimal(output_tokens) * output_rate


def test_cost_calculation_math():
    # Scenario 1: standard tokens
    # Input: 2000 tokens ($0.00030), Output: 500 tokens ($0.00030) -> Total $0.00060
    cost_1 = calculate_cost(2000, 500)
    assert cost_1 == Decimal("0.000600")

    # Scenario 2: zero tokens
    cost_2 = calculate_cost(0, 0)
    assert cost_2 == Decimal("0.0")

    # Scenario 3: large token usage
    # Input: 100,000, Output: 20,000 -> 100k*0.15e-6 + 20k*0.60e-6 = 0.015 + 0.012 = 0.027
    cost_3 = calculate_cost(100000, 20000)
    assert cost_3 == Decimal("0.027000")
