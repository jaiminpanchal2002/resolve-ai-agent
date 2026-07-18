import pytest

import resolveai.agent.graph as graph_module
from resolveai.agent.graph import (
    AgentState,
    Severity,
    TicketCategory,
    TicketClassification,
    classify_node,
)
from resolveai.core.llm_provider import FakeProvider


def _base_state(messages: list[dict[str, str]]) -> AgentState:
    return AgentState(
        ticket_id="TKT-12345",
        run_id="RUN-12345",
        customer_id=None,
        messages=messages,
        classification=None,
        plan=None,
        tool_outputs=[],
        policy_citations=[],
        guardrail_violations=[],
        resolution=None,
        reason=None,
        evidence=[],
        actions_taken=[],
        input_tokens=0,
        output_tokens=0,
        estimated_cost=0,
        latency_ms=0,
    )


class _StubProvider(FakeProvider):
    """Returns a crafted classification so we can assert node behavior."""

    async def generate_structured(
        self, prompt, response_model, system_instruction=None, temperature=0.0
    ):
        if response_model is TicketClassification:
            return (
                TicketClassification(
                    category=TicketCategory.DELIVERY_DISPUTE,
                    severity=Severity.HIGH,
                    intent="REPORT_MISSING_DELIVERY",
                    requires_account_data=True,
                ),
                12,
                8,
            )
        return await super().generate_structured(
            prompt, response_model, system_instruction, temperature
        )


@pytest.mark.asyncio
async def test_classify_node_extracts_customer_id(monkeypatch):
    monkeypatch.setattr(graph_module, "get_llm_provider", lambda: _StubProvider())
    state = _base_state(
        [
            {
                "role": "customer",
                "content": (
                    "My laptop shows delivered but I haven't received it. "
                    "Customer ID CUS-10293"
                ),
            }
        ]
    )

    result = await classify_node(state, db=None)

    assert isinstance(result["classification"], TicketClassification)
    assert result["classification"].category == TicketCategory.DELIVERY_DISPUTE
    assert result["classification"].requires_account_data is True
    # Real logic under test: regex extraction of the customer id from free text
    assert result["customer_id"] == "CUS-10293"
    assert result["input_tokens"] > 0
    assert result["output_tokens"] > 0


@pytest.mark.asyncio
async def test_classify_node_without_customer_id(monkeypatch):
    monkeypatch.setattr(graph_module, "get_llm_provider", lambda: _StubProvider())
    state = _base_state([{"role": "customer", "content": "I never got my parcel."}])

    result = await classify_node(state, db=None)

    assert result["customer_id"] is None
    assert result["classification"].severity == Severity.HIGH


def test_classification_rejects_invalid_category():
    with pytest.raises(ValueError):
        TicketClassification(
            category="NOT_A_REAL_CATEGORY",
            severity="MEDIUM",
            intent="X",
            requires_account_data=False,
        )
