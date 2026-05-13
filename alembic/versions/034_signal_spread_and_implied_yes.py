"""signals + event_market_analysis: add spread_at_signal + implied_yes_probability

Revision ID: 034
Revises: 033
Create Date: 2026-05-13

Two analysis-grade fields the J+30 retro will need that we currently
don't capture:

1. `signals.spread_at_signal` — the bid-ask spread (in price points,
   e.g. 0.0250 = 2.5 pp) at the moment the signal was emitted. The
   `realistic_replay.py` harness today assumes a flat 3 pp spread
   across all markets, which is wrong for liquid Polymarket markets
   (typically 1 pp) and underestimates illiquid ones (5 pp+). Without
   per-signal capture we cannot split RTP by liquidity tier.

2. `signals.implied_yes_probability` (and the matching
   `event_market_analysis.implied_yes_probability`) — the LLM's own
   estimate of P(YES) after the news, which v2 emits in the JSON
   output but we currently throw away after using it for the
   direction decision. Persisting it unlocks calibration metrics
   (Brier score, reliability diagram) — answer to "is the LLM
   systematically over/under-confident?".

Both columns nullable. Legacy rows (pre-deploy) stay NULL — no
backfill because the values aren't recoverable.

Safety: pure additive ADD COLUMN nullable, no rewrite, no lock.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "signals",
        sa.Column("spread_at_signal", sa.Numeric(5, 4), nullable=True),
    )
    op.add_column(
        "signals",
        sa.Column("implied_yes_probability", sa.Numeric(4, 3), nullable=True),
    )
    op.add_column(
        "event_market_analysis",
        sa.Column("implied_yes_probability", sa.Numeric(4, 3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("event_market_analysis", "implied_yes_probability")
    op.drop_column("signals", "implied_yes_probability")
    op.drop_column("signals", "spread_at_signal")
