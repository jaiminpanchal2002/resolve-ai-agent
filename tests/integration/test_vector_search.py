import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from resolveai.models.models import Policy, PolicyChunk
from resolveai.services.retrieval import RetrievalService


@pytest.mark.asyncio
async def test_pgvector_cosine_distance_search(db_session: AsyncSession):
    # 1. Insert two policies
    p1 = Policy(id="POL-SHIPPING", title="Shipping Rules", category="logistics")
    p2 = Policy(id="POL-BILLING", title="Billing Rules", category="payments")
    db_session.add_all([p1, p2])
    await db_session.flush()

    # Create dummy embeddings of settings.EMBEDDING_DIMENSION (1536)
    # Vector A: [0.9] followed by [0.0]s
    emb_a = [0.0] * 1536
    emb_a[0] = 0.9
    
    # Vector B: [0.1] followed by [0.0]s
    emb_b = [0.0] * 1536
    emb_b[0] = 0.1

    chunk1 = PolicyChunk(
        policy_id="POL-SHIPPING",
        content="Shipping rules state that items are delivered within five business days.",
        embedding=emb_a,
        chunk_index=0
    )
    chunk2 = PolicyChunk(
        policy_id="POL-BILLING",
        content="Billing rules state that refunds take 3-5 banking days to clear.",
        embedding=emb_b,
        chunk_index=0
    )
    db_session.add_all([chunk1, chunk2])
    await db_session.flush()

    # 2. Query closest to emb_a
    service = RetrievalService(db_session)
    
    # We query with a vector closer to Vector A (e.g. [0.8] followed by 0.0s)
    query_emb = [0.0] * 1536
    query_emb[0] = 0.8
    
    # Mock llm_provider.get_embedding to return query_emb
    import unittest.mock as mock
    service.provider.get_embedding = mock.AsyncMock(return_value=query_emb)

    results = await service.retrieve_semantic(query="dummy", limit=1)

    # 3. Assert shipping chunk comes first since it has the closer embedding
    assert len(results) == 1
    assert results[0][0].policy_id == "POL-SHIPPING"
    assert "five business days" in results[0][0].content
