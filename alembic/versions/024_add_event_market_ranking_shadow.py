"""add event_market_ranking_shadow table.

Revision ID: 024
Revises: 023
Create Date: 2026-04-25

Table records the top-k output of the *opposite* ranking variant (v1 in prod
→ store v2, and vice versa) so operators can compare divergence before
flipping the `ranking_variant_event_to_market` flag. Rows are write-once,
idempotent via the UNIQUE (event_id, variant, rank) constraint.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_market_ranking_shadow",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("market_id", sa.Text(), nullable=False),
        sa.Column("variant", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("rrf_score", sa.Float(), nullable=False),
        sa.Column("cosine_score", sa.Float(), nullable=True),
        sa.Column("entity_matches", sa.Integer(), nullable=True),
        sa.Column("date_proximity", sa.Float(), nullable=True),
        sa.Column("bucket_match", sa.Boolean(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.CheckConstraint("variant IN ('v1','v2')", name="ck_ranking_shadow_variant"),
        sa.UniqueConstraint(
            "event_id", "variant", "rank",
            name="uq_ranking_shadow_event_variant_rank",
        ),
    )
    op.create_index(
        "ix_ranking_shadow_event_variant",
        "event_market_ranking_shadow",
        ["event_id", "variant"],
    )


def downgrade() -> None:
    op.drop_index("ix_ranking_shadow_event_variant", table_name="event_market_ranking_shadow")
    op.drop_table("event_market_ranking_shadow")
