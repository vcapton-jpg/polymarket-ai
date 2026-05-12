"""shadow_signals + shadow_signal_outcomes — record rejected signals for ML.

Revision ID: 033
Revises: 032
Create Date: 2026-05-12

Today filters (T-001 BUY_NO×YES<0.30, T-013 BUY_NO×YES≥0.70) reject ~5-15
candidate signals per day BEFORE they reach `signals`. capture_price only
runs on persisted `signals` rows, so we never label what happened to the
rejected ones. Result: 19 765 LLM analyses / 30 d but only 754 labeled
signals (96 % of ML training data discarded by survivor bias — see
docs/measurements/realistic_backtest_2026-05-12.md).

This migration adds a parallel "shadow" pipeline:
  - `shadow_signals`         — minimal record of each filter-rejected
                                candidate: direction, market price at
                                rejection, why it was rejected.
  - `shadow_signal_outcomes` — the same 4-checkpoint capture
                                (t+5min / t+15min / t+1h / t+24h) so the
                                rejected candidates get labeled too.

Two tables instead of "one table with a `is_shadow` flag" because the
FK shape is different and we want zero risk of mixing shadow rows
into user-facing endpoints by accident.

The signal-builder writes to `shadow_signals` via a Celery dispatch
(see `app/workers/tasks_shadow.py`). Feature-flagged off by default
(`enable_shadow_capture=False`) — flip via `.env` after verifying the
table doesn't blow up under load.

Safety: pure additive ADD TABLE, no index/lock on existing tables.
Safe on any prod state.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shadow_signals",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "event_id",
            sa.Integer,
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "market_id",
            sa.Text,
            sa.ForeignKey("markets.market_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column(
            "market_price_at_signal",
            sa.Numeric(6, 4),
            nullable=False,
        ),
        sa.Column("rejection_reason", sa.String(50), nullable=False),
        sa.Column("llm_model_version", sa.String(50), nullable=True),
        sa.Column("signal_score", sa.Numeric(5, 1), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_shadow_signals_created_at",
        "shadow_signals",
        ["created_at"],
    )
    op.create_index(
        "ix_shadow_signals_rejection_reason",
        "shadow_signals",
        ["rejection_reason"],
    )

    op.create_table(
        "shadow_signal_outcomes",
        sa.Column(
            "shadow_signal_id",
            sa.BigInteger,
            sa.ForeignKey("shadow_signals.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("price_t5min",  sa.Numeric(6, 4), nullable=True),
        sa.Column("price_t15min", sa.Numeric(6, 4), nullable=True),
        sa.Column("price_t1h",    sa.Numeric(6, 4), nullable=True),
        sa.Column("price_t24h",   sa.Numeric(6, 4), nullable=True),
        sa.Column("move_t5min_pct",  sa.Numeric(7, 4), nullable=True),
        sa.Column("move_t15min_pct", sa.Numeric(7, 4), nullable=True),
        sa.Column("move_t1h_pct",    sa.Numeric(7, 4), nullable=True),
        sa.Column("move_t24h_pct",   sa.Numeric(7, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("shadow_signal_outcomes")
    op.drop_index("ix_shadow_signals_rejection_reason", table_name="shadow_signals")
    op.drop_index("ix_shadow_signals_created_at", table_name="shadow_signals")
    op.drop_table("shadow_signals")
