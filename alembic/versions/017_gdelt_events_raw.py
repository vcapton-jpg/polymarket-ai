"""create gdelt_events_raw staging table

Revision ID: 017
Revises: 016
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gdelt_events_raw",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("gdelt_event_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor1", sa.Text(), nullable=True),
        sa.Column("actor2", sa.Text(), nullable=True),
        sa.Column("event_code", sa.String(length=10), nullable=True),
        sa.Column("tone", sa.Float(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_gdelt_events_raw_published_at",
        "gdelt_events_raw",
        ["published_at"],
        postgresql_ops={"published_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("ix_gdelt_events_raw_published_at", table_name="gdelt_events_raw")
    op.drop_table("gdelt_events_raw")
