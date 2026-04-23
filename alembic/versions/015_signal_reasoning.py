"""add reasoning + llm_model_version + source_tier_mix to signals; create signals_pending_reasoning

Revision ID: 015
Revises: 014
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signals", sa.Column("reasoning", sa.Text(), nullable=True))
    op.add_column("signals", sa.Column("llm_model_version", sa.String(length=50), nullable=True))
    op.add_column("signals", sa.Column("source_tier_mix", postgresql.JSONB(), nullable=True))

    op.create_table(
        "signals_pending_reasoning",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("market_id", sa.Text(), nullable=False),
        sa.Column("inputs", postgresql.JSONB(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_signals_pending_reasoning_created_at",
        "signals_pending_reasoning",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_signals_pending_reasoning_created_at", table_name="signals_pending_reasoning")
    op.drop_table("signals_pending_reasoning")
    op.drop_column("signals", "source_tier_mix")
    op.drop_column("signals", "llm_model_version")
    op.drop_column("signals", "reasoning")
