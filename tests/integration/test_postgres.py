import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from resolveai.models.models import Customer, Ticket, AgentRun

@pytest.mark.asyncio
async def test_postgres_crud_operations(db_session: AsyncSession):
    # 1. Create a customer
    c = Customer(id="CUS-INTEGRATION", name="Alex Carter", email="alex@example.com")
    db_session.add(c)
    await db_session.flush()
    
    # 2. Create a ticket linked to customer
    t = Ticket(id="TKT-INTEGRATION", customer_id="CUS-INTEGRATION", status="OPEN")
    db_session.add(t)
    await db_session.flush()
    
    # 3. Assert they are fetchable
    stmt_cust = select(Customer).where(Customer.id == "CUS-INTEGRATION")
    res_cust = await db_session.execute(stmt_cust)
    fetched_cust = res_cust.scalar_one_or_none()
    
    assert fetched_cust is not None
    assert fetched_cust.name == "Alex Carter"
    assert fetched_cust.email == "alex@example.com"
    
    # Fetch ticket
    stmt_tkt = select(Ticket).where(Ticket.id == "TKT-INTEGRATION")
    res_tkt = await db_session.execute(stmt_tkt)
    fetched_tkt = res_tkt.scalar_one_or_none()
    
    assert fetched_tkt is not None
    assert fetched_tkt.customer_id == "CUS-INTEGRATION"
    assert fetched_tkt.status == "OPEN"
