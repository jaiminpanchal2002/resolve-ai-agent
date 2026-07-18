import unittest.mock as mock

import pytest

from resolveai.agent.graph import (
    AgentState,
    Severity,
    TicketCategory,
    TicketClassification,
    finalize_escalation_node,
    route_after_guardrails,
)


def _state_with_violations(violations: list[str]) -> AgentState:
    return AgentState(
        ticket_id="TKT-123",
        run_id="RUN-123",
        customer_id="CUS-123",
        messages=[
            {"role": "customer", "content": "My laptop shows delivered but I haven't received it."}
        ],
        classification=TicketClassification(
            category=TicketCategory.DELIVERY_DISPUTE,
            severity=Severity.HIGH,
            intent="REPORT_MISSING_DELIVERY",
            requires_account_data=True,
        ),
        plan=[],
        tool_outputs=[],
        policy_citations=["POL-DELIVERY-04"],
        guardrail_violations=violations,
        resolution=None,
        reason=None,
        evidence=[],
        actions_taken=["Created escalation ESC-100"],
        input_tokens=0,
        output_tokens=0,
        estimated_cost=0,
        latency_ms=0,
    )


def test_routing_sends_violations_to_deterministic_escalation():
    state = _state_with_violations(["Order value > 50,000 and missing proof of delivery."])
    assert route_after_guardrails(state) == "finalize_escalation"


def test_routing_sends_clean_state_to_llm_response():
    state = _state_with_violations([])
    assert route_after_guardrails(state) == "generate_response"


@pytest.mark.asyncio
async def test_finalize_escalation_propagates_citations_and_violations():
    violation = "Order value > 50,000 and missing proof of delivery."
    state = _state_with_violations([violation])

    result = await finalize_escalation_node(state, mock.AsyncMock())

    # Escalation is deterministic — no LLM call can override a guardrail
    assert result["resolution"] == "ESCALATE"
    assert "POL-DELIVERY-04" in result["evidence"]
    assert violation in result["evidence"]
    assert violation in result["reason"]
