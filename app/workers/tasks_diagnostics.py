"""Operational diagnostics, run by Celery beat.

Read-only — no DB writes, no external calls. Each function emits a
single structured INFO log line so an operator can grep the worker
logs and see the trend over time without standing up a separate
metrics pipeline.

Wired into beat in `app/workers/celery_app.py`:
  * ``clustering-diversity-hourly``         → emit_diversity_distribution
  * ``signals-bucket-direction-daily``      → emit_signals_outcome_distribution
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select

from app.db.database import get_session_factory
from app.db.models import Event, Signal, SignalOutcome
from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_session_factory():
    """Indirection so tests can swap in a test-DB factory."""
    return get_session_factory()


async def _emit_diversity_distribution() -> dict[int, int]:
    session_factory = _get_session_factory()
    async with session_factory() as s:
        rows = (
            await s.execute(
                select(Event.unique_sources_count, func.count(Event.id))
                .group_by(Event.unique_sources_count)
                .order_by(Event.unique_sources_count)
            )
        ).all()
    distribution = {int(v or 0): int(c) for v, c in rows}
    total = sum(distribution.values()) or 1
    pct = {k: round(100 * v / total, 1) for k, v in distribution.items()}
    logger.info(
        "clustering.diversity total=%d distribution=%s pct=%s",
        total,
        distribution,
        pct,
    )
    return distribution


@celery_app.task(name="app.workers.tasks_diagnostics.emit_diversity_distribution")
def emit_diversity_distribution() -> dict[int, int]:
    return _run_async(_emit_diversity_distribution())


# ──────────────────────────────────────────────────────────────────────────
# bucket × direction × outcome distribution
#
# Audit follow-up (2026-04-28): the 27-04 retro showed geopolitics×BUY_NO
# was responsible for 7 catastrophic losses on news-binary markets while
# politics×BUY_NO was the strongest performer. Without this metric the
# pattern was only visible by hand-querying the DB. Emitting daily means
# any future rotation in bucket performance is visible in the worker log
# immediately.
# ──────────────────────────────────────────────────────────────────────────


async def _emit_signals_outcome_distribution(window_days: int = 7) -> list[dict]:
    """Group last `window_days` of signals by (bucket, direction) and emit
    win-rate + expectancy at the 1h horizon. Skips signals without a
    `price_t1h` (still inside the resolution window).

    Win-rate is computed from the **signed** move on the underlying price
    (positive = directionally correct), not the raw move_pct. That keeps
    the metric stable for both BUY_YES and BUY_NO.

    Expectancy is the proper per-bet ROI:
       BUY_YES  →  (price_t1h − entry) / entry
       BUY_NO   →  (entry − price_t1h) / (1 − entry)
    so a -100% loss is the worst case (you lose your stake), preventing
    the inflated `move_pct` figures from poisoning the average.
    """
    session_factory = _get_session_factory()
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    # `price_t1h` IS NOT NULL is the gate that excludes signals still
    # inside the resolution window. Buckets with all-None outcomes drop
    # out entirely, which is what we want.
    is_win = case(
        (
            Signal.direction == "BUY_YES",
            (SignalOutcome.price_t1h > Signal.market_price_at_signal),
        ),
        else_=(SignalOutcome.price_t1h < Signal.market_price_at_signal),
    )
    roi_pct = case(
        (
            Signal.direction == "BUY_YES",
            (SignalOutcome.price_t1h - Signal.market_price_at_signal)
            / func.nullif(Signal.market_price_at_signal, 0),
        ),
        else_=(Signal.market_price_at_signal - SignalOutcome.price_t1h)
        / func.nullif(1 - Signal.market_price_at_signal, 0),
    ) * 100

    async with session_factory() as s:
        rows = (
            await s.execute(
                select(
                    Event.bucket,
                    Signal.direction,
                    func.count().label("n"),
                    func.sum(case((is_win, 1), else_=0)).label("wins"),
                    func.avg(roi_pct).label("avg_roi_pct"),
                )
                .join(Event, Event.id == Signal.event_id)
                .join(SignalOutcome, SignalOutcome.signal_id == Signal.id)
                .where(
                    Signal.created_at >= cutoff,
                    SignalOutcome.price_t1h.isnot(None),
                    Signal.market_price_at_signal.isnot(None),
                    Signal.market_price_at_signal > 0,
                    Signal.market_price_at_signal < 1,
                )
                .group_by(Event.bucket, Signal.direction)
                .order_by(func.count().desc())
            )
        ).all()

    summary: list[dict] = []
    for bucket, direction, n, wins, avg_roi in rows:
        wr = (float(wins) / float(n) * 100.0) if n else 0.0
        expect = float(avg_roi) if avg_roi is not None else 0.0
        summary.append(
            {
                "bucket": bucket or "(none)",
                "direction": direction,
                "n": int(n),
                "win_rate_1h_pct": round(wr, 1),
                "expectancy_1h_pct": round(expect, 2),
            }
        )

    logger.info(
        "signals.outcome window_days=%d rows=%s",
        window_days,
        summary,
    )
    return summary


@celery_app.task(
    name="app.workers.tasks_diagnostics.emit_signals_outcome_distribution"
)
def emit_signals_outcome_distribution(window_days: int = 7) -> list[dict]:
    return _run_async(_emit_signals_outcome_distribution(window_days))
