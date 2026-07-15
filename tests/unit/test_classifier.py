import pytest
from resolveai.agent.graph import classify_node, AgentState, TicketClassification
from resolveai.core.config import settings

@pytest.mark.asyncio
async def test_classify_node_success():
    # Setup state
    state = AgentState(
        ticket_id="TKT-12345",
        run_id="RUN-12345",
        customer_id=None,
        messages=[
            {"role": "customer", "content": "My laptop shows delivered but I haven't received it. Customer ID CUS-10293"}
        ],
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
    
    # Run node
    result = await classify_node(state, db=None)
    
    # Assert
    assert result["classification"] is not None
    assert isinstance(result["classification"], TicketClassification)
    assert result["classification"].category == "DELIVERY_DISPUTE"
    assert result["classification"].requires_account_data is True
    # Customer ID extraction assert
    assert result["customer_id"] == "CUS-10293"
    assert result["input_tokens"] > 0
    assert result["output_tokens"] > 0
