"""Retention task — periodic DELETE of stale rows from large/growing tables.

Without retention, growth at observed rates (2026-05-06 audit):
  - news:               ~16 k rows/month
  - news_clean:         ~12 k rows/month (CASCADE-linked to news)
  - events:             ~13 k rows/month
  - event_market_candidates: ~50 k rows/month
  - event_market_ranking_shadow: ~30 k rows/month
  - llm_cost_log:       ~370 k rows/month  ← biggest

would push the DB past 50 GB inside 6 months and bloat the HNSW indexes
with rows that signals will never look back at.

This task runs nightly (the beat schedule entry at celery_app.py adds it
on the `default` queue). Each DELETE batch is bounded by
`max_per_table_per_run` so a single nightly run can never hold a long
exclusive lock — at the bound of 5 000 rows / table the task tail is
< 30 s wall-clock total, well under any healthcheck horizon.

Policies:
  - news / news_clean : 90 d on news.ingestion_date (CASCADE removes
    news_clean rows). Keeps the rolling 3-month corpus we backtest on.
  - events            : 180 d on events.last_seen. We keep events twice
    as long as raw news because the same event may be referenced by
    signals + outcomes that we still want to inspect.
  - event_market_candidates / event_market_ranking_shadow / event_market_features
                      : 30 d. These are operational snapshots — the
    LLM analyses (event_market_analysis) and the persisted signals are
    where the lasting value lives.
  - llm_cost_log      : 30 d on raw rows; aggregate to a daily rollup
    (deferred to a follow-up task — for now we just bound the table).

Safety: per-table SELECT count(*) BEFORE the DELETE so the log line is
auditable; aborts if any single DELETE exceeds 50 % of the table (an
unexpected over-delete almost always means a buggy WHERE clause and we
prefer a noisy abort to a silent purge).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.db.database import get_session_factory
from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# Per-table caps — one nightly run never deletes more than this many
# rows from a single table. Set high enough to keep up with steady-state
# growth (~5 k/day for the largest tables) but low enough that locks
# stay short.
MAX_PER_TABLE_PER_RUN = 5_000


# (table, age_column, retention_days) — order matters: parents first so
# CASCADE rows are already gone before we hit the dependents.
RETENTION_POLICIES = [
    ("news", "ingestion_date", 90),  # news_clean cascades from this
    ("events", "last_seen", 180),
    ("event_market_candidates", "created_at", 30),
    ("event_market_ranking_shadow", "created_at", 30),
    ("event_market_features", "created_at", 30),
    ("llm_cost_log", "created_at", 30),
    ("agent_activities", "created_at", 30),
]


@celery_app.task(bind=True, max_retries=1)
def run_retention(self):
    try:
        return _run_async(_run_retention_async())
    except Exception as exc:
        logger.exception("run_retention failed")
        raise self.retry(exc=exc, throw=False) from exc


async def _run_retention_async() -> dict:
    async_session_factory = get_session_factory()

    summary: dict = {"deleted_per_table": {}, "skipped_safety": []}
    now = datetime.now(UTC)

    async with async_session_factory() as session:
        for table, age_col, retention_days in RETENTION_POLICIES:
            cutoff = now - timedelta(days=retention_days)

            # Count before — for both the log line and the safety check.
            try:
                total = (
                    await session.execute(
                        text(f"SELECT count(*) FROM {table}")
                    )
                ).scalar() or 0
                eligible = (
                    await session.execute(
                        text(
                            f"SELECT count(*) FROM {table} "
                            f"WHERE {age_col} < :cutoff"
                        ),
                        {"cutoff": cutoff},
                    )
                ).scalar() or 0
            except Exception as e:
                # Missing column or table → log and skip (not all tables
                # exist on every dev environment).
                logger.warning(
                    "retention: pre-count for %s failed: %s — skipping", table, e
                )
                continue

            if eligible == 0:
                summary["deleted_per_table"][table] = 0
                continue

            # Safety: if eligible > 50 % of the table, the WHERE clause
            # is almost certainly wrong (timezone bug, type mismatch,
            # etc.). Bail loud rather than purge half the table.
            if total > 100 and eligible > total * 0.5:
                logger.error(
                    "retention SAFETY ABORT on %s: eligible=%d > 50%% of total=%d "
                    "— refusing to delete; check the policy",
                    table, eligible, total,
                )
                summary["skipped_safety"].append(table)
                continue

            # Bounded delete in a single statement. PostgreSQL doesn't
            # have LIMIT in DELETE directly; use the IN-subselect form.
            try:
                result = await session.execute(
                    text(
                        f"""
                        DELETE FROM {table}
                        WHERE ctid IN (
                            SELECT ctid FROM {table}
                            WHERE {age_col} < :cutoff
                            LIMIT :batch_cap
                        )
                        """
                    ),
                    {"cutoff": cutoff, "batch_cap": MAX_PER_TABLE_PER_RUN},
                )
                await session.commit()
                deleted = result.rowcount or 0
                summary["deleted_per_table"][table] = deleted
                logger.info(
                    "retention %s: deleted %d (eligible total %d, "
                    "table size %d, retention %dd)",
                    table, deleted, eligible, total, retention_days,
                )
            except Exception as e:
                await session.rollback()
                logger.error("retention DELETE on %s failed: %s", table, e)
                summary["deleted_per_table"][table] = -1

    return {"status": "ok", **summary}
