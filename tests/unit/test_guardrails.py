import unittest.mock as mock

import pytest

from resolveai.agent.graph import AgentState, TicketClassification, guardrails_node


@pytest.mark.asyncio
async def test_guardrail_refund_limit_violation():
    # Setup state with a high refund amount (₹55,000)
    state = AgentState(
        ticket_id="TKT-123",
        run_id="RUN-123",
        customer_id="CUS-123",
        messages=[],
        classification=TicketClassification(
            category="PAYMENT_ISSUE",
            severity="MEDIUM",
            intent="REQUEST_REFUND",
            requires_account_data=True,
        ),
        plan=[],
        tool_outputs=[
            # Mock successful refund request of 55000 INR
            {
                "tool": "create_refund_request",
                "input": {"order_id": "ORD-123", "amount": 55000.0},
                "status": "SUCCESS",
                "output": {"status": "SUCCESS"},
            }
        ],
        policy_citations=[],
        guardrail_violations=[],
        resolution=None,
        reason=None,
        evidence=[],
        actions_taken=["Applied planning steps"],
        input_tokens=0,
        output_tokens=0,
        estimated_cost=0,
        latency_ms=0,
    )

    # Mock database session
    mock_db = mock.AsyncMock()

    # Run guardrails node
    result = await guardrails_node(state, mock_db)

    # Assert
    assert len(result["guardrail_violations"]) == 1
    assert "exceeds maximum allowed auto-approval limit" in result["guardrail_violations"][0]
    # Check that escalation was created
    assert any("Created escalation" in act for act in result["actions_taken"])


@pytest.mark.asyncio
async def test_guardrail_missing_delivery_violation():
    state = AgentState(
        ticket_id="TKT-123",
        run_id="RUN-123",
        customer_id="CUS-123",
        messages=[],
        classification=TicketClassification(
            category="DELIVERY_DISPUTE",
            severity="HIGH",
            intent="REPORT_MISSING_DELIVERY",
            requires_account_data=True,
        ),
        plan=[],
        tool_outputs=[
            {
                "tool": "get_order",
                "input": {"order_id": "ORD-999"},
                "status": "SUCCESS",
                "output": {"total_amount": 82000.0},
            },
            {
                "tool": "get_shipment",
                "input": {"order_id": "ORD-999"},
                "status": "SUCCESS",
                "output": {"proof_of_delivery": "Missing", "signature_captured": False},
            },
        ],
        policy_citations=["POL-DELIVERY-04"],
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

    mock_db = mock.AsyncMock()
    result = await guardrails_node(state, mock_db)

    assert len(result["guardrail_violations"]) == 1
    assert "proof of delivery is missing" in result["guardrail_violations"][0]
    assert any("Created escalation" in act for act in result["actions_taken"])


@pytest.mark.asyncio
async def test_guardrail_no_violations():
    state = AgentState(
        ticket_id="TKT-123",
        run_id="RUN-123",
        customer_id="CUS-123",
        messages=[],
        classification=TicketClassification(
            category="PAYMENT_ISSUE",
            severity="LOW",
            intent="REQUEST_REFUND",
            requires_account_data=True,
        ),
        plan=[],
        tool_outputs=[
            {
                "tool": "create_refund_request",
                "input": {"order_id": "ORD-123", "amount": 12500.0},
                "status": "SUCCESS",
                "output": {"status": "SUCCESS"},
            }
        ],
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

    mock_db = mock.AsyncMock()
    result = await guardrails_node(state, mock_db)

    assert len(result["guardrail_violations"]) == 0
