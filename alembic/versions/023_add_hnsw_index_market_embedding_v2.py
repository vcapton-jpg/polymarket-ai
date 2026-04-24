"""Add HNSW index on markets.embedding_v2 — required before market-surface v2 promotion.

Revision ID: 023
Revises: 022
Create Date: 2026-04-24

NOT auto-applied by `alembic upgrade head` in CI — this migration is applied
manually, per the runbook, only once the market surface is ready to be flipped
to v2. Without it, `vector_retriever.search_markets_by_embedding` does a
sequential scan on `embedding_v2` and latency blows up.
"""

from __future__ import annotations

from alembic import op


revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_markets_embedding_v2_hnsw "
            "ON markets USING hnsw (embedding_v2 vector_cosine_ops)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_markets_embedding_v2_hnsw")
