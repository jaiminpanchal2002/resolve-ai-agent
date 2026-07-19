import os

os.environ.setdefault("USE_FAKE_LLM", "true")

import asyncio
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from resolveai.models.models import (
    Base,
    Customer,
    Order,
    Payment,
    Policy,
    PolicyChunk,
    Shipment,
)


# 1. Spin up ephemeral Postgres and Redis containers for the session
@pytest.fixture(scope="session")
def postgres_container():
    # Use the official pgvector-enabled Postgres container image
    container = PostgresContainer("ankane/pgvector:v0.5.1")
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def redis_container():
    container = RedisContainer("redis:7-alpine")
    container.start()
    try:
        yield container
    finally:
        container.stop()


# 2. Configure event loop for session scope
@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# 3. Session-scoped test engine with auto-schema creation
@pytest.fixture(scope="session")
def test_sync_engine(postgres_container):
    # Fetch connection details from container
    db_url = postgres_container.get_connection_url()
    # Force psycopg driver (v3) for sync migrations / seeding
    if "://" in db_url:
        db_url = "postgresql+psycopg://" + db_url.split("://", 1)[1]
    engine = create_engine(db_url)

    # Enable vector extension and create tables
    with engine.begin() as conn:
        # Alembic equivalent: create extension vector
        from sqlalchemy import text

        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(conn)

    return engine


@pytest_asyncio.fixture
async def test_async_engine(postgres_container, test_sync_engine):
    db_url = postgres_container.get_connection_url()
    # Force asyncpg driver for async operations
    if "://" in db_url:
        db_url = "postgresql+asyncpg://" + db_url.split("://", 1)[1]

    engine = create_async_engine(db_url)
    yield engine
    await engine.dispose()


# 4. Transaction-isolated database session fixture
@pytest_asyncio.fixture
async def db_session(test_async_engine):
    session_factory = async_sessionmaker(
        bind=test_async_engine, expire_on_commit=False, autoflush=False
    )

    # Savepoint transaction: rolls back after the test completes
    async with session_factory() as session, session.begin():
        yield session
        await session.rollback()


# 5. Seeding helper fixtures for tools and integration tests
@pytest_asyncio.fixture
async def seeded_db(db_session):
    # Insert mock customer
    c = Customer(id="CUS-10293", name="Tracey Miller", email="tracey@example.com")
    db_session.add(c)

    # Insert mock high-value order (₹82,000)
    o_high = Order(
        id="ORD-9999",
        customer_id="CUS-10293",
        status="DELIVERED",
        total_amount=Decimal("82000.00"),
        currency="INR",
    )
    db_session.add(o_high)

    # Insert mock payment
    p_high = Payment(
        id="PAY-9999",
        order_id="ORD-9999",
        status="SUCCESS",
        amount=Decimal("82000.00"),
        currency="INR",
        provider="stripe",
    )
    db_session.add(p_high)

    # Insert mock shipment with missing proof of delivery (to trigger guardrails)
    s_high = Shipment(
        id="SHP-193",
        order_id="ORD-9999",
        status="DELIVERED",
        carrier="Delhivery",
        tracking_number="TRK9999",
        proof_of_delivery_url=None,  # missing
        signature_captured=False,  # missing
    )
    db_session.add(s_high)

    # Insert policies
    pol = Policy(id="POL-DELIVERY-04", title="Missing Delivery Rules", category="logistics")
    db_session.add(pol)
    await db_session.flush()

    chunk = PolicyChunk(
        policy_id="POL-DELIVERY-04",
        content=(
            "Orders above ₹50,000 with missing proof of delivery must be "
            "escalated to the logistics investigation team."
        ),
        embedding=[0.1] * 1536,
        chunk_index=0,
    )
    db_session.add(chunk)

    await db_session.flush()
    return db_session
