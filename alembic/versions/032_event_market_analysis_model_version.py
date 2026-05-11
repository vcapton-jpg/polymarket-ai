"""event_market_analysis: add llm_model_version

Revision ID: 032
Revises: 031
Create Date: 2026-05-11

T-011 in docs/PLAN_30D_SIGNAL_QUALITY.md. The `signals.llm_model_version`
column has existed since the initial schema but was always written as
NULL — audit on prod 2026-05-11 found 732/732 signals with NULL. Root
cause: the column is set from `analysis.llm_model_version` propagated
out of `event_market_analysis`, but `event_market_analysis` never had
the column in the first place, so the entire chain was carrying None.

Adding the column here, defaulting NULL for the ~17k existing rows.
The writer in `app/workers/tasks_scoring.py` is patched in the same
PR to record `analyzer._model` (= `settings.openai_impact_model`) at
each LLM call, and `_build_llm_data` propagates it through to the
SignalBuilder so new signals carry the value end-to-end.

Why now: this is the prereq for Sprint 2 — without it we cannot
compare RTP between gpt-4o-mini (current default) and any future
model swap (gpt-4o, claude, etc.) on the same prod traffic.
Splitting metrics by `llm_model_version` needs the column populated.

Safety: pure additive ADD COLUMN nullable, no rewrite, no lock beyond
the brief catalog update. Safe on any table size.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "event_market_analysis",
        sa.Column("llm_model_version", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("event_market_analysis", "llm_model_version")
