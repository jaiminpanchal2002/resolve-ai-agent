import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from resolveai.agent.tools import (
    get_customer,
    get_order,
    get_payment,
    get_shipment,
    search_policy,
    create_refund_request,
    create_escalation,
)


@pytest.mark.asyncio
async def test_agent_read_tools(seeded_db: AsyncSession):
    # Test get_customer
    cust_res = await get_customer(seeded_db, "CUS-10293")
    assert "error" not in cust_res
    assert cust_res["name"] == "Tracey Miller"

    # Test get_order
    order_res = await get_order(seeded_db, "ORD-9999")
    assert "error" not in order_res
    assert order_res["total_amount"] == 82000.0

    # Test get_shipment
    ship_res = await get_shipment(seeded_db, "ORD-9999")
    assert "error" not in ship_res
    assert ship_res["proof_of_delivery"] == "Missing"
    assert ship_res["signature_captured"] is False


@pytest.mark.asyncio
async def test_agent_write_tools(seeded_db: AsyncSession):
    # Test create_refund_request
    refund_res = await create_refund_request(seeded_db, "ORD-9999", 82000.0, "Proof of delivery missing")
    assert refund_res["status"] == "SUCCESS"
    assert refund_res["amount"] == 82000.0

    # Test create_escalation
    esc_res = await create_escalation(
        seeded_db, 
        ticket_id="TKT-EVAL-TEST", 
        agent_run_id="RUN-EVAL-TEST", 
        queue_name="Logistics Queue", 
        reason="Missing proof of delivery"
    )
    assert esc_res["status"] == "PENDING"
    assert esc_res["queue_name"] == "Logistics Queue"
    assert esc_res["escalation_id"].startswith("ESC-")
