"""Add columns present in ORM but missing from migrations.

- markets.bucket (String(50), nullable, indexed)
- signals.cosine_score (Numeric(5,4), nullable)
- event_market_analysis.specificity_score (Numeric(3,2), nullable)

Revision ID: 004
Revises: 003
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def _col_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.scalar() is not None


def _idx_exists(conn, idx: str) -> bool:
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :i"),
        {"i": idx},
    )
    return result.scalar() is not None


def upgrade() -> None:
    conn = op.get_bind()

    if not _col_exists(conn, "markets", "bucket"):
        op.add_column("markets", sa.Column("bucket", sa.String(50), nullable=True))
    if not _idx_exists(conn, "ix_markets_bucket"):
        op.create_index("ix_markets_bucket", "markets", ["bucket"])

    if not _col_exists(conn, "signals", "cosine_score"):
        op.add_column("signals", sa.Column("cosine_score", sa.Numeric(5, 4), nullable=True))

    if not _col_exists(conn, "event_market_analysis", "specificity_score"):
        op.add_column("event_market_analysis", sa.Column("specificity_score", sa.Numeric(3, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("event_market_analysis", "specificity_score")
    op.drop_column("signals", "cosine_score")
    op.drop_index("ix_markets_bucket", table_name="markets")
    op.drop_column("markets", "bucket")
