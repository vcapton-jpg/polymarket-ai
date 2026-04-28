"""Add `country_residence` (ISO 3166-1 alpha-2) to user_profiles.

Revision ID: 027
Revises: 026
Create Date: 2026-04-28

Audit follow-up (Legal-PR-1, B3): Foresight signs Polymarket trades on
behalf of users via the Builder Program. Polymarket itself geo-blocks
US (CFTC) and a handful of sanctioned countries. Without a declared
residence we cannot honour those blocks at signup, which exposes us to
regulatory complicity. New column captures the user-declared country at
registration time. NULL is allowed only because pre-027 rows pre-date
the field — the API enforces the value going forward.

The column is unindexed: it's read in two places (registration and
admin/audit reports), and a btree index on a 2-char column has no value
under typical row counts. We keep it as plain VARCHAR(2) without a
CHECK constraint so future jurisdictional copy changes can't be blocked
by a schema migration.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("country_residence", sa.String(length=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "country_residence")
