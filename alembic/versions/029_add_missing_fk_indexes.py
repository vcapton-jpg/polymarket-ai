"""Add btree indexes on every foreign-key column that lacked one.

Revision ID: 029
Revises: 028
Create Date: 2026-05-05

Audit follow-up 2026-05-05 (M3). Postgres does NOT auto-index FK
columns — only the *referenced* PK is indexed. Without a child-side
index, every cascading delete on the parent does a sequential scan
of the child table, and every "list all rows for parent X" query
does the same. Today the affected tables are tiny (`positions`,
`orders`, `paper_positions` are all in the low thousands), but
`markets` is at 192 k and growing, so a `DELETE FROM markets WHERE
…` already triggers four seq scans per child table.

Indexes added (all `IF NOT EXISTS`, all `CONCURRENTLY`, btree):

  * `positions.portfolio_id`            — list "open positions for X"
  * `positions.market_id`               — cascade from markets DELETE
  * `orders.portfolio_id`               — order history per user
  * `orders.market_id`                  — cascade from markets DELETE
  * `orders.signal_id`                  — find orders backed by a signal
  * `daily_briefs.user_id`              — show user's brief history
  * `api_keys_b2b.user_id`              — show user's API keys
  * `event_market_features.market_id`   — cascade from markets DELETE
                                          (the composite (event_id,
                                          market_id) covers event_id
                                          alone via leftmost-prefix
                                          but not market_id alone)
  * `outcome_views.signal_id`           — same reasoning vs (user_id,
                                          signal_id) composite
  * `paper_positions.signal_id`         — orders attributed to signal
  * `paper_positions.market_id`         — cascade from markets DELETE

Not added (already covered):
  * `signals.event_id` — covered by composite (event_id, market_id)
    via leftmost-prefix.
  * `signals.market_id` — covered by `ix_signals_market_created`
    (market_id, created_at).
  * `paper_positions.user_id` — `ix_paper_positions_user` exists.
  * `signal_outcomes.signal_id` — it IS the PK.
  * `event_market_features.event_id` — leftmost prefix of composite.
  * `outcome_views.user_id` — leftmost prefix of composite.

`CONCURRENTLY` is mandatory — production tables are not locked while
the index builds. Each index is created in its own implicit
autocommit transaction (alembic's `autocommit_block` handles the
no-transaction-block requirement of `CREATE INDEX CONCURRENTLY`).

Idempotent: re-running this migration on a partially-applied or
freshly-seeded DB is a no-op for any index that already exists.
"""

from __future__ import annotations

from alembic import op


revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


# (index_name, table, column) — kept as a flat list so the upgrade /
# downgrade pair stay symmetric and a future "add one more" change
# touches exactly two lines.
_INDEXES: list[tuple[str, str, str]] = [
    ("ix_positions_portfolio_id", "positions", "portfolio_id"),
    ("ix_positions_market_id", "positions", "market_id"),
    ("ix_orders_portfolio_id", "orders", "portfolio_id"),
    ("ix_orders_market_id", "orders", "market_id"),
    ("ix_orders_signal_id", "orders", "signal_id"),
    ("ix_daily_briefs_user_id", "daily_briefs", "user_id"),
    ("ix_api_keys_b2b_user_id", "api_keys_b2b", "user_id"),
    ("ix_event_market_features_market_id", "event_market_features", "market_id"),
    ("ix_outcome_views_signal_id", "outcome_views", "signal_id"),
    ("ix_paper_positions_signal_id", "paper_positions", "signal_id"),
    ("ix_paper_positions_market_id", "paper_positions", "market_id"),
]


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for index_name, table, column in _INDEXES:
            op.execute(
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name} "
                f"ON {table} ({column})"
            )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for index_name, _table, _column in _INDEXES:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}")
