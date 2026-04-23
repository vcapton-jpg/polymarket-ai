"""signal_articles: per-(signal × variant) article audit trail.

Revision ID: 021
Revises: 020
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_articles",
        sa.Column(
            "signal_id",
            sa.BigInteger,
            sa.ForeignKey("signals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("variant", sa.String(64), nullable=False),
        sa.Column(
            "news_clean_id",
            sa.BigInteger,
            sa.ForeignKey("news_clean.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rank", sa.SmallInteger, nullable=False),
        sa.Column("score", sa.Numeric(6, 4), nullable=False),
        sa.Column("cosine_score", sa.Numeric(6, 4), nullable=False),
        sa.Column("recency_weight", sa.Numeric(6, 4), nullable=False),
        sa.Column("excerpt", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint(
            "signal_id", "variant", "news_clean_id",
            name="pk_signal_articles",
        ),
    )
    op.create_index(
        "idx_sa_signal_variant",
        "signal_articles",
        ["signal_id", "variant"],
    )
    op.create_index(
        "idx_sa_news_clean",
        "signal_articles",
        ["news_clean_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_sa_news_clean", table_name="signal_articles")
    op.drop_index("idx_sa_signal_variant", table_name="signal_articles")
    op.drop_table("signal_articles")
