"""Drop unused `gdelt_events_raw` table.

Revision ID: 030
Revises: 029
Create Date: 2026-05-05

Audit follow-up 2026-05-05. Migration 017 introduced
`gdelt_events_raw` with the intent of capturing the raw GDELT v2
event records before mapping them into `news`. The mapping path
(`tasks_ingestion.fetch_gdelt`) was implemented but it inserts
straight into `news` (with `source_tier=3`); nothing in the codebase
ever writes to `gdelt_events_raw`, and nothing reads from it either.
Verified live before drop: `SELECT COUNT(*) FROM gdelt_events_raw`
returned 0 rows.

Drop is non-`CONCURRENTLY` because `DROP TABLE` does not support
that clause; the table is unused so the brief `AccessExclusiveLock`
contention is irrelevant. The accompanying ORM model (`GdeltEventRaw`)
and its Index are removed from `app/db/models.py` in the same PR.

Downgrade re-creates the empty schema as it was post-017 in case a
future reviewer wants to revisit the "raw GDELT capture" design —
but does NOT restore data (there was none).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_gdelt_events_raw_published_at", table_name="gdelt_events_raw")
    op.drop_table("gdelt_events_raw")


def downgrade() -> None:
    op.create_table(
        "gdelt_events_raw",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("gdelt_event_id", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor1", sa.Text(), nullable=True),
        sa.Column("actor2", sa.Text(), nullable=True),
        sa.Column("event_code", sa.String(length=10), nullable=True),
        sa.Column("avg_tone", sa.Float(), nullable=True),
        sa.Column("goldstein_scale", sa.Float(), nullable=True),
        sa.Column("num_mentions", sa.Integer(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("gdelt_event_id", name="uq_gdelt_events_raw_event_id"),
    )
    op.create_index(
        "ix_gdelt_events_raw_published_at",
        "gdelt_events_raw",
        [sa.text("published_at DESC")],
    )
