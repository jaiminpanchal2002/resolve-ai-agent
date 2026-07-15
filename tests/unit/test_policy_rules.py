import pytest
import unittest.mock as mock
from resolveai.agent.graph import generate_response_node, AgentState, TicketClassification

@pytest.mark.asyncio
async def test_policy_citation_propagation():
    state = AgentState(
        ticket_id="TKT-123",
        run_id="RUN-123",
        customer_id="CUS-123",
        messages=[
            {"role": "customer", "content": "My laptop shows delivered but I haven't received it."}
        ],
        classification=TicketClassification(
            category="DELIVERY_DISPUTE",
            severity="HIGH",
            intent="REPORT_MISSING_DELIVERY",
            requires_account_data=True
        ),
        plan=[],
        tool_outputs=[
            {
                "tool": "search_policy",
                "input": {"query": "delivery dispute policy"},
                "status": "SUCCESS",
                "output": {
                    "citations": ["POL-DELIVERY-04"],
                    "results": [{"policy_id": "POL-DELIVERY-04", "content": "High-value delivery rule..."}]
                }
            }
        ],
        policy_citations=["POL-DELIVERY-04"],
        guardrail_violations=["Order value > 50,000 and missing proof of delivery."],
        resolution=None,
        reason=None,
        evidence=[],
        actions_taken=["Created escalation ESC-100"],
        input_tokens=0,
        output_tokens=0,
        estimated_cost=0,
        latency_ms=0,
    )
    
    mock_db = mock.AsyncMock()
    result = await generate_response_node(state, mock_db)
    
    # Assert final response node forces ESCALATE and includes all policy citations and guardrail violations as evidence
    assert result["resolution"] == "ESCALATE"
    assert "POL-DELIVERY-04" in result["evidence"]
    assert "Order value > 50,000 and missing proof of delivery." in result["evidence"]
