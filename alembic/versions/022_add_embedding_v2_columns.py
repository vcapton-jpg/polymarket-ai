"""add embedding_v2 columns to news_clean / markets / events.

Revision ID: 022
Revises: 021
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


_TABLES = ("news_clean", "markets", "events")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("embedding_v2", Vector(1536), nullable=True))
        op.add_column(table, sa.Column("embedding_v2_composition", sa.Text(), nullable=True))
        op.add_column(
            table,
            sa.Column(
                "embedding_v2_computed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "embedding_v2_computed_at")
        op.drop_column(table, "embedding_v2_composition")
        op.drop_column(table, "embedding_v2")
