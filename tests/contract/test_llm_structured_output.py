import pytest

from resolveai.agent.graph import TicketClassification
from resolveai.core.llm_provider import get_llm_provider


@pytest.mark.asyncio
async def test_llm_provider_structured_contract():
    provider = get_llm_provider()

    prompt = "Please classify a customer saying: 'I want to cancel my subscription.'"

    classification, in_tokens, out_tokens = await provider.generate_structured(
        prompt=prompt,
        response_model=TicketClassification,
        system_instruction="You are a classifier.",
    )

    # Contract asserts: must yield an instance of TicketClassification conforming to schemas
    assert isinstance(classification, TicketClassification)
    assert classification.category in [
        "PAYMENT_ISSUE",
        "DELIVERY_DISPUTE",
        "ACCOUNT_ACCESS",
        "SUBSCRIPTION_CHANGE",
        "POLICY_VIOLATION",
        "AMBIGUOUS",
    ]
    assert classification.severity in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert isinstance(classification.requires_account_data, bool)
    assert isinstance(classification.intent, str)
