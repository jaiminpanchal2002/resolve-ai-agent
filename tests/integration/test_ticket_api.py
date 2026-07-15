import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from resolveai.main import resolveai
from resolveai.db.session import get_async_db
from resolveai.core.auth import get_password_hash
from resolveai.models.models import User, Customer


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession):
    # Override get_async_db dependency to use the testcontainer transaction session
    def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_async_db] = override_get_db
    
    # Register a default admin user and customer so security checks pass
    stmt = select_user = select_user_stmt = None
    from sqlalchemy import select
    res = await db_session.execute(select(User).where(User.email == "admin@resolveai.com"))
    if not res.scalar_one_or_none():
        user = User(email="admin@resolveai.com", hashed_password=get_password_hash("admin123"), role="admin")
        db_session.add(user)
        
    res_cust = await db_session.execute(select(Customer).where(Customer.id == "CUS-10293"))
    if not res_cust.scalar_one_or_none():
        cust = Customer(id="CUS-10293", name="Jane", email="jane@example.com")
        db_session.add(cust)
        
    await db_session.flush()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
        
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_auth_and_ticket_flow(api_client: AsyncClient):
    # 1. Login to get token
    login_data = {
        "username": "admin@resolveai.com",
        "password": "admin123"
    }
    auth_resp = await api_client.post("/api/auth/token", data=login_data)
    assert auth_resp.status_code == 200
    token_json = auth_resp.json()
    token = token_json["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Ingest a Ticket
    ticket_payload = {
        "customer_id": "CUS-10293",
        "customer_name": "Jane",
        "messages": [
            {"sender": "customer", "body": "My package ORD-123 shows delivered but I never received it."}
        ]
    }
    
    # We run it synchronously (async_run=False) so we get immediate outcomes in test
    create_resp = await api_client.post("/api/tickets?async_run=false", json=ticket_payload, headers=headers)
    assert create_resp.status_code == 200
    create_json = create_resp.json()
    ticket_id = create_json["ticket_id"]
    assert ticket_id.startswith("TKT-")

    # 3. List Tickets
    list_resp = await api_client.get("/api/tickets", headers=headers)
    assert list_resp.status_code == 200
    tickets_list = list_resp.json()
    assert any(t["id"] == ticket_id for t in tickets_list)

    # 4. Fetch Ticket Details
    detail_resp = await api_client.get(f"/api/tickets/{ticket_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail_json = detail_resp.json()
    assert detail_json["id"] == ticket_id
    assert len(detail_json["messages"]) == 1

    # 5. Submit Human Review
    review_payload = {
        "status": "APPROVED",
        "feedback": "Agent decision complies with POL-DELIVERY-04 guidelines."
    }
    review_resp = await api_client.post(f"/api/tickets/{ticket_id}/review", json=review_payload, headers=headers)
    assert review_resp.status_code == 200
    
    # Assert review matches in detail view
    detail_resp_2 = await api_client.get(f"/api/tickets/{ticket_id}", headers=headers)
    assert detail_resp_2.json()["human_review"]["status"] == "APPROVED"
