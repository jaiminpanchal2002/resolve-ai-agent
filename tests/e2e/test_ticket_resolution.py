import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from resolveai.agent.graph import run_agent
from resolveai.models.models import (
    AgentDecision,
    AgentRun,
    Escalation,
    Ticket,
    TicketMessage,
    ToolCall,
)


@pytest.mark.asyncio
async def test_full_ticket_resolution_e2e(seeded_db: AsyncSession):
    # 1. Create a customer ticket mimicking the delivery dispute scenario
    # Customer Tracey Miller (CUS-10293) has order ORD-9999 (value ₹82,000)
    # The shipment has status DELIVERED but proof of delivery is Missing.
    t = Ticket(id="TKT-E2E-MISSING-LAPTOP", customer_id="CUS-10293", status="OPEN")
    seeded_db.add(t)

    # Customer message
    m = TicketMessage(
        ticket_id="TKT-E2E-MISSING-LAPTOP",
        sender="customer",
        body="My laptop shows delivered but I haven't received it. It was order ORD-9999.",
    )
    seeded_db.add(m)
    await seeded_db.flush()

    # 2. Run the agent graph on the ticket
    result = await run_agent("TKT-E2E-MISSING-LAPTOP", seeded_db)

    # 3. Assert outputs
    assert result["ticket_id"] == "TKT-E2E-MISSING-LAPTOP"
    assert result["resolution"] == "ESCALATE"
    assert "POL-DELIVERY-04" in result["evidence"] or len(result["evidence"]) > 0
    assert any("Created escalation" in act for act in result["actions_taken"])

    # 4. Assert database persistence of audit logs
    run_id = result["run_id"]

    # Verify AgentRun record exists
    stmt_run = select(AgentRun).where(AgentRun.id == run_id)
    run_rec = (await seeded_db.execute(stmt_run)).scalar_one_or_none()
    assert run_rec is not None
    assert run_rec.status == "COMPLETED"

    # Verify ToolCalls were audited (we expect get_order, get_shipment, search_policy, etc.)
    stmt_tools = select(ToolCall).where(ToolCall.agent_run_id == run_id)
    tool_recs = (await seeded_db.execute(stmt_tools)).scalars().all()
    assert len(tool_recs) > 0
    tool_names = [t.tool_name for t in tool_recs]
    assert (
        "get_order" in tool_names or "get_shipment" in tool_names or "search_policy" in tool_names
    )

    # Verify AgentDecision record exists
    stmt_dec = select(AgentDecision).where(AgentDecision.agent_run_id == run_id)
    dec_rec = (await seeded_db.execute(stmt_dec)).scalar_one_or_none()
    assert dec_rec is not None
    assert dec_rec.resolution == "ESCALATE"

    # Verify Escalation record exists in DB
    stmt_esc = select(Escalation).where(Escalation.agent_run_id == run_id)
    esc_rec = (await seeded_db.execute(stmt_esc)).scalar_one_or_none()
    assert esc_rec is not None
    assert esc_rec.status == "PENDING"
