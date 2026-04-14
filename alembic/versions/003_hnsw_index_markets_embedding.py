"""Create HNSW index on markets.embedding for fast cosine search.

Revision ID: 003
Revises: 002
"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_markets_embedding_hnsw
        ON markets USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_markets_embedding_hnsw;")
