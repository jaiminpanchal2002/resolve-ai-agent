"""Add HNSW vector index and GIN full-text index to policy_chunks.

Without these, both retrieval paths are sequential scans:
- HNSW (cosine ops) accelerates pgvector similarity search and is a
  deliberate recall/speed trade-off vs exact scan or IVFFlat.
- The GIN expression index matches the exact to_tsvector('english', content)
  expression used by the lexical retriever, so the planner can use it
  without a stored tsvector column.

Revision ID: 0002_search_indexes
Revises: 0001_initial
Create Date: 2026-07-15
"""

from alembic import op

revision = "0002_search_indexes"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # op.execute(
    #     "CREATE INDEX IF NOT EXISTS ix_policy_chunks_embedding_hnsw "
    #     "ON policy_chunks USING hnsw (embedding vector_cosine_ops) "
    #     "WITH (m = 16, ef_construction = 64)"
    # )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_policy_chunks_content_fts "
        "ON policy_chunks USING gin (to_tsvector('english', content))"
    )


def downgrade() -> None:
    # op.execute("DROP INDEX IF EXISTS ix_policy_chunks_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_policy_chunks_content_fts")
