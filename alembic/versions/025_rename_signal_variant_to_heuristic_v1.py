"""Rename variant='signal' → 'heuristic_v1' in signal_predictions.

Revision ID: 025
Revises: 024
Create Date: 2026-04-24

Chantier #5: the legacy 'signal' name (written by chantier #1's record_baselines)
is renamed to 'heuristic_v1' so it sits next to baseline_* and any future
heuristic_shadow / heuristic_v2 variants with a consistent naming scheme.

This is a pure data migration — no DDL — and idempotent: re-running on
already-migrated data is a no-op (UPDATE affects 0 rows the second time).
"""
from __future__ import annotations

from alembic import op


revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE signal_predictions SET variant = 'heuristic_v1' WHERE variant = 'signal'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE signal_predictions SET variant = 'signal' WHERE variant = 'heuristic_v1'"
    )
