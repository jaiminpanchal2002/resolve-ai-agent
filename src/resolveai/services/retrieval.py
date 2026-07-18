import logging
import time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from resolveai.core.llm_provider import get_llm_provider
from resolveai.models.models import Policy, PolicyChunk

logger = logging.getLogger(__name__)

# Global variable to cache the cross-encoder model to prevent reloading
_cross_encoder_model: Any = None


def get_cross_encoder() -> Any:
    global _cross_encoder_model
    if _cross_encoder_model is None:
        try:
            from sentence_transformers import CrossEncoder

            # Load lightweight cross-encoder (CPU-friendly)
            _cross_encoder_model = CrossEncoder(
                "cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu"
            )
            logger.info("Loaded CrossEncoder model successfully.")
        except Exception as e:
            logger.warning(
                f"Could not load sentence-transformers CrossEncoder: {e}. "
                "Reranking will use fallback."
            )
            _cross_encoder_model = "fallback"
    return _cross_encoder_model


class RetrievalService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.provider = get_llm_provider()

    async def retrieve_semantic(
        self, query: str, limit: int = 10, category_filter: str | None = None
    ) -> list[tuple[PolicyChunk, Policy]]:
        """Retrieve policy chunks using cosine similarity computed in Python."""
        embedding = await self.provider.get_embedding(query)

        stmt = select(PolicyChunk, Policy).join(Policy, PolicyChunk.policy_id == Policy.id)

        if category_filter:
            stmt = stmt.where(Policy.category == category_filter)

        result = await self.db.execute(stmt)
        all_chunks = list(result.all())

        # Compute cosine similarity in python
        # cosine distance = 1 - (A . B) / (||A|| ||B||)
        def cosine_distance(vec_a, vec_b):
            import math
            if not vec_a or not vec_b:
                return 1.0
            dot_product = sum(a * b for a, b in zip(vec_a, vec_b, strict=True))
            norm_a = math.sqrt(sum(a * a for a in vec_a))
            norm_b = math.sqrt(sum(b * b for b in vec_b))
            if norm_a == 0 or norm_b == 0:
                return 1.0
            return 1.0 - (dot_product / (norm_a * norm_b))

        scored_chunks = []
        for chunk, policy in all_chunks:
            dist = cosine_distance(chunk.embedding, embedding)
            scored_chunks.append((chunk, policy, dist))

        # Sort by distance ascending
        scored_chunks.sort(key=lambda x: x[2])
        return [(chunk, policy) for chunk, policy, dist in scored_chunks[:limit]]

    async def retrieve_lexical(
        self, query: str, limit: int = 10, category_filter: str | None = None
    ) -> list[tuple[PolicyChunk, Policy]]:
        """Retrieve policy chunks using PostgreSQL Full-Text Search with ILIKE fallback."""
        stmt = select(PolicyChunk, Policy).join(Policy, PolicyChunk.policy_id == Policy.id)

        if category_filter:
            stmt = stmt.where(Policy.category == category_filter)

        # Build clean FTS condition. We split words to create a search query.
        cleaned_words = [w for w in query.replace("'", "").split() if len(w) > 2]
        fts_query = " & ".join(cleaned_words)

        if fts_query:
            # Match tsvector of content against websearch_to_tsquery or standard tsquery
            stmt = stmt.where(
                func.to_tsvector("english", PolicyChunk.content).op("@@")(
                    func.to_tsquery("english", fts_query)
                )
            ).limit(limit)
        else:
            # Fallback to simple ILIKE if search query is too short/empty
            stmt = stmt.where(PolicyChunk.content.ilike(f"%{query}%")).limit(limit)

        result = await self.db.execute(stmt)
        results_list = list(result.all())

        # If FTS returns nothing, perform simple word-based ILIKE fallback
        if not results_list and cleaned_words:
            fallback_stmt = select(PolicyChunk, Policy).join(
                Policy, PolicyChunk.policy_id == Policy.id
            )
            if category_filter:
                fallback_stmt = fallback_stmt.where(Policy.category == category_filter)

            # OR-chain ILIKE queries
            conditions = [PolicyChunk.content.ilike(f"%{w}%") for w in cleaned_words[:3]]
            from sqlalchemy import or_

            fallback_stmt = fallback_stmt.where(or_(*conditions)).limit(limit)
            fallback_result = await self.db.execute(fallback_stmt)
            results_list = list(fallback_result.all())

        return results_list

    async def retrieve_hybrid(
        self, query: str, limit: int = 5, category_filter: str | None = None
    ) -> list[tuple[PolicyChunk, Policy, float]]:
        """Combine semantic and lexical results using Reciprocal Rank Fusion (RRF)."""
        # Fetch twice the limit to have enough overlap for RRF
        retrieval_limit = limit * 2

        semantic_list = await self.retrieve_semantic(
            query, limit=retrieval_limit, category_filter=category_filter
        )
        lexical_list = await self.retrieve_lexical(
            query, limit=retrieval_limit, category_filter=category_filter
        )

        # RRF Scoring Map: key is (chunk_id) -> (chunk, policy, score)
        rrf_scores: dict[int, tuple[PolicyChunk, Policy, float]] = {}

        # Process Semantic results (rank 1-indexed)
        for rank, (chunk, policy) in enumerate(semantic_list, start=1):
            chunk_id = chunk.id
            score = 1.0 / (60.0 + rank)
            rrf_scores[chunk_id] = (chunk, policy, score)

        # Process Lexical results
        for rank, (chunk, policy) in enumerate(lexical_list, start=1):
            chunk_id = chunk.id
            score = 1.0 / (60.0 + rank)
            if chunk_id in rrf_scores:
                # Add score if already present
                c, p, current_score = rrf_scores[chunk_id]
                rrf_scores[chunk_id] = (c, p, current_score + score)
            else:
                rrf_scores[chunk_id] = (chunk, policy, score)

        # Sort by score descending and return the top items matching limit
        sorted_results = sorted(rrf_scores.values(), key=lambda x: x[2], reverse=True)
        return sorted_results[:limit]

    async def retrieve_hybrid_reranked(
        self, query: str, limit: int = 5, category_filter: str | None = None
    ) -> list[tuple[PolicyChunk, Policy, float]]:
        """Rerank hybrid retrieval outcomes using Cross-Encoder."""
        # Retrieve hybrid candidates (e.g. limit * 3 candidates)
        candidates = await self.retrieve_hybrid(
            query, limit=limit * 3, category_filter=category_filter
        )
        if not candidates:
            return []

        model = get_cross_encoder()

        if model == "fallback" or model is None:
            # Fallback to pure RRF ordering if CrossEncoder didn't load
            logger.debug("Falling back to RRF ordering (Cross-Encoder unavailable).")
            return candidates[:limit]

        # Format input for cross-encoder model: list of [query, document_text]
        pairs = [[query, chunk.content] for chunk, policy, rrf_score in candidates]

        try:
            # Compute similarity score
            scores = model.predict(pairs)

            # Associate scores with candidates
            scored_candidates = []
            for idx, score in enumerate(scores):
                chunk, policy, rrf_score = candidates[idx]
                scored_candidates.append((chunk, policy, float(score)))

            # Sort by Cross-Encoder score descending
            scored_candidates.sort(key=lambda x: x[2], reverse=True)
            return scored_candidates[:limit]
        except Exception as e:
            logger.error(f"Error during Cross-Encoder reranking: {e}")
            return candidates[:limit]


# Retrieval evaluation helper to measure Recall@5, MRR, Latency
async def evaluate_retrieval_performance(
    db: AsyncSession,
    test_cases: list[
        dict[str, Any]
    ],  # List of dicts with {"query": str, "expected_policy_id": str}
) -> dict[str, dict[str, float]]:
    """Run a retrieval audit comparing Vector, Hybrid, and Hybrid+Rerank."""
    service = RetrievalService(db)
    metrics = {
        "Vector": {"recall": 0.0, "mrr": 0.0, "latency_ms": 0.0},
        "Hybrid": {"recall": 0.0, "mrr": 0.0, "latency_ms": 0.0},
        "Hybrid + Rerank": {"recall": 0.0, "mrr": 0.0, "latency_ms": 0.0},
    }

    num_cases = len(test_cases)
    if num_cases == 0:
        return metrics

    for method in ["Vector", "Hybrid", "Hybrid + Rerank"]:
        total_latency = 0.0
        recall_hits = 0
        mrr_sum = 0.0

        for case in test_cases:
            query = case["query"]
            expected_id = case["expected_policy_id"]

            start_time = time.perf_counter()
            if method == "Vector":
                results = await service.retrieve_semantic(query, limit=5)
                # Unwrap results format
                chunks = [r[0] for r in results]
            elif method == "Hybrid":
                results = await service.retrieve_hybrid(query, limit=5)
                chunks = [r[0] for r in results]
            else:  # Hybrid + Rerank
                results = await service.retrieve_hybrid_reranked(query, limit=5)
                chunks = [r[0] for r in results]
            duration = (time.perf_counter() - start_time) * 1000.0

            total_latency += duration

            # Calculate Recall@5 and MRR
            policy_ids = [chunk.policy_id for chunk in chunks]

            # Check for hit
            if expected_id in policy_ids:
                recall_hits += 1
                rank = policy_ids.index(expected_id) + 1
                mrr_sum += 1.0 / rank

        metrics[method]["recall"] = recall_hits / num_cases
        metrics[method]["mrr"] = mrr_sum / num_cases
        metrics[method]["latency_ms"] = total_latency / num_cases

    return metrics
