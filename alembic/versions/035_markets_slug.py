"""markets: add slug (fixes broken Polymarket deep links)

Revision ID: 035
Revises: 034
Create Date: 2026-05-19

Every "Voir sur Polymarket" link was broken: the API emitted
`https://polymarket.com/market/<conditionId>`, which 307-redirects to
`/404`. Polymarket's web app only resolves `https://polymarket.com/
event/<slug>`. We already receive the slug from Gamma `/events`
(event-level + market-level) but discarded it.

This adds a nullable `markets.slug`. Gamma ingestion now persists it
on both create and update, so existing rows backfill themselves within
one ingest cycle (active markets are continuously re-fetched). The URL
builder falls back to `https://polymarket.com` (never a 404) while a
row's slug is still NULL.

Nullable + no backfill DDL — zero-downtime, no lock on a large table.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "markets",
        sa.Column("slug", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("markets", "slug")
