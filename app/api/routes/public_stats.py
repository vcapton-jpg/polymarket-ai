"""Public marketing stats — `GET /api/stats/public`, no auth.

Replaces the hardcoded `frontend/src/lib/stats.ts PUBLIC_STATS` block.
The Homepage / Login / Portfolio pages read live values from this
endpoint so AMF / DGCCRF can never catch us with promotional figures
that don't match the actual database state (Legal-PR-3, audit
finding B8 + H1 + H3).

Honest empty-state contract: every field returned here is computed
from a real query. If the database is empty (fresh deploy, beta
phase) the field returns 0 / null and the frontend renders
"—" / "Lancement en bêta" / a skeleton — never a fabricated number.

The endpoint is unauthenticated. Counters revealed (total signals,
total markets, distinct traders / 7 d) are intentional marketing
inputs and contain no user-identifying data. A trivial 60 s
in-process cache caps the cost — these queries scan small tables
and a once-per-minute round-trip per worker is negligible.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db_session
from app.db.models import Market, Position, Signal, SignalOutcome


router = APIRouter(prefix="/stats", tags=["stats"])


class PublicStatsOut(BaseModel):
    # Pipeline-level counters (always populated even on a fresh DB).
    signals_today: int
    signals_total: int
    markets_monitored: int
    # Engagement signal — distinct user_ids opening a position over the
    # last 7 days. Returns 0 when no real-money trades have happened.
    active_traders_week: int
    # Pipeline freshness — minutes since the most recent signal, or null
    # when the DB has no signals yet.
    last_signal_minutes_ago: Optional[int]
    # Quality signal — direction-correct ratio at +1h horizon over the
    # last 30 days. Returns null + n=0 until at least 30 resolved
    # signals exist (any narrower sample is too noisy to publish).
    win_rate_1h_pct: Optional[float]
    win_rate_sample_size: int
    win_rate_window_days: int


_CACHE: dict[str, object] = {"data": None, "expires_at": 0.0}
_CACHE_TTL_SECONDS = 60.0
WIN_RATE_WINDOW_DAYS = 30
WIN_RATE_MIN_SAMPLE = 30


async def _compute_public_stats(db: AsyncSession) -> PublicStatsOut:
    """One pass of the four small queries the endpoint exposes. Each is
    bounded by either a primary-key scan or an indexed `created_at`
    range so the total cost is sub-millisecond on the production DB.
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_cutoff = now - timedelta(days=7)
    win_rate_cutoff = now - timedelta(days=WIN_RATE_WINDOW_DAYS)

    signals_today = (
        await db.execute(
            select(func.count(Signal.id)).where(Signal.created_at >= today_start)
        )
    ).scalar_one()

    signals_total = (
        await db.execute(select(func.count(Signal.id)))
    ).scalar_one()

    markets_monitored = (
        await db.execute(select(func.count(Market.market_id)))
    ).scalar_one()

    last_signal_at = (
        await db.execute(select(func.max(Signal.created_at)))
    ).scalar_one_or_none()
    last_signal_minutes_ago: Optional[int] = None
    if last_signal_at is not None:
        delta = now - last_signal_at
        last_signal_minutes_ago = max(0, int(delta.total_seconds() // 60))

    # Engagement: distinct user_ids on Position rows in the last 7 days.
    # Joins via Portfolio's user_id; absent positions table is fine — the
    # COUNT returns 0.
    from app.db.models import Portfolio

    active_traders_week = (
        await db.execute(
            select(func.count(distinct(Portfolio.user_id)))
            .select_from(Position)
            .join(Portfolio, Portfolio.id == Position.portfolio_id)
            .where(Position.opened_at >= week_cutoff)
        )
    ).scalar_one()

    # Win rate at 1h horizon — proper signed-move computation. Only
    # publish when the sample is meaningful (≥30 resolved signals) so
    # we don't ship a noisy "100%" with n=2.
    sample_size_q = await db.execute(
        select(func.count(Signal.id))
        .join(SignalOutcome, SignalOutcome.signal_id == Signal.id)
        .where(
            Signal.created_at >= win_rate_cutoff,
            SignalOutcome.price_t1h.isnot(None),
            Signal.market_price_at_signal.isnot(None),
            Signal.market_price_at_signal > 0,
            Signal.market_price_at_signal < 1,
        )
    )
    win_rate_sample_size = sample_size_q.scalar_one()

    win_rate_1h_pct: Optional[float] = None
    if win_rate_sample_size >= WIN_RATE_MIN_SAMPLE:
        wins_q = await db.execute(
            select(func.count(Signal.id))
            .join(SignalOutcome, SignalOutcome.signal_id == Signal.id)
            .where(
                Signal.created_at >= win_rate_cutoff,
                SignalOutcome.price_t1h.isnot(None),
                Signal.market_price_at_signal.isnot(None),
                Signal.market_price_at_signal > 0,
                Signal.market_price_at_signal < 1,
                # BUY_YES → price went up; BUY_NO → price went down
                (
                    (
                        (Signal.direction == "BUY_YES")
                        & (SignalOutcome.price_t1h > Signal.market_price_at_signal)
                    )
                    | (
                        (Signal.direction == "BUY_NO")
                        & (SignalOutcome.price_t1h < Signal.market_price_at_signal)
                    )
                ),
            )
        )
        wins = wins_q.scalar_one()
        win_rate_1h_pct = round(100.0 * wins / win_rate_sample_size, 1)

    return PublicStatsOut(
        signals_today=int(signals_today),
        signals_total=int(signals_total),
        markets_monitored=int(markets_monitored),
        active_traders_week=int(active_traders_week),
        last_signal_minutes_ago=last_signal_minutes_ago,
        win_rate_1h_pct=win_rate_1h_pct,
        win_rate_sample_size=int(win_rate_sample_size),
        win_rate_window_days=WIN_RATE_WINDOW_DAYS,
    )


@router.get("/public", response_model=PublicStatsOut)
async def get_public_stats(db: AsyncSession = Depends(get_db_session)) -> PublicStatsOut:
    """Live marketing counters. 60 s in-process cache shared across
    workers (each worker holds its own cache; the hit rate at typical
    homepage load patterns is high enough that cache coherence isn't
    worth a Redis round-trip)."""
    now = time.monotonic()
    cached = _CACHE.get("data")
    expires = float(_CACHE.get("expires_at", 0.0))
    if isinstance(cached, PublicStatsOut) and now < expires:
        return cached

    data = await _compute_public_stats(db)
    _CACHE["data"] = data
    _CACHE["expires_at"] = now + _CACHE_TTL_SECONDS
    return data


def _reset_cache_for_tests() -> None:
    """Drop the cache so each unit test starts clean."""
    _CACHE["data"] = None
    _CACHE["expires_at"] = 0.0
