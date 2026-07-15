import unittest.mock as mock
import pytest
from resolveai.services.retrieval import RetrievalService
from resolveai.models.models import Policy, PolicyChunk

@pytest.mark.asyncio
async def test_rrf_scoring_and_ranking():
    # Instantiate RetrievalService with a mock DB
    mock_db = mock.AsyncMock()
    service = RetrievalService(mock_db)
    
    # Create mock chunks
    chunk_a = PolicyChunk(id=1, policy_id="POL-1", content="Chunk A Content", chunk_index=0)
    chunk_b = PolicyChunk(id=2, policy_id="POL-2", content="Chunk B Content", chunk_index=0)
    policy_a = Policy(id="POL-1", title="Policy 1", category="general")
    policy_b = Policy(id="POL-2", title="Policy 2", category="general")
    
    # Mock retrieval methods
    # Semantic: A is 1st (rank 1), B is 2nd (rank 2)
    service.retrieve_semantic = mock.AsyncMock(return_value=[
        (chunk_a, policy_a),
        (chunk_b, policy_b)
    ])
    # Lexical: A is 2nd (rank 2), B is 1st (rank 1)
    service.retrieve_lexical = mock.AsyncMock(return_value=[
        (chunk_b, policy_b),
        (chunk_a, policy_a)
    ])
    
    # Run hybrid retrieval (RRF)
    # Expected scores:
    # A score = 1/(60+1) + 1/(60+2) = 1/61 + 1/62 = 0.016393 + 0.016129 = 0.032522
    # B score = 1/(60+2) + 1/(60+1) = 1/62 + 1/61 = 0.032522
    # Both are equal, but let's check sorting behavior.
    
    # Now let's change semantic to only return A (rank 1), and lexical to only return B (rank 1)
    service.retrieve_semantic = mock.AsyncMock(return_value=[(chunk_a, policy_a)])
    service.retrieve_lexical = mock.AsyncMock(return_value=[(chunk_b, policy_b)])
    
    results = await service.retrieve_hybrid(query="test", limit=5)
    
    # Assert
    assert len(results) == 2
    # A has rank 1 in semantic -> score = 1/61 = 0.016393
    # B has rank 1 in lexical -> score = 1/61 = 0.016393
    assert results[0][2] == pytest.approx(1.0 / 61.0)
    
    # Now make A overlap and rank higher: Semantic A (rank 1), B (rank 2); Lexical A (rank 1), B (rank 2)
    service.retrieve_semantic = mock.AsyncMock(return_value=[(chunk_a, policy_a), (chunk_b, policy_b)])
    service.retrieve_lexical = mock.AsyncMock(return_value=[(chunk_a, policy_a), (chunk_b, policy_b)])
    
    results_overlap = await service.retrieve_hybrid(query="test", limit=5)
    
    # A score = 1/61 + 1/61 = 2/61 = 0.032786
    # B score = 1/62 + 1/62 = 2/62 = 0.032258
    # A must be ranked first
    assert results_overlap[0][0].id == chunk_a.id
    assert results_overlap[1][0].id == chunk_b.id
    assert results_overlap[0][2] == pytest.approx(2.0 / 61.0)
    assert results_overlap[1][2] == pytest.approx(2.0 / 62.0)
