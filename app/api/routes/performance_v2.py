"""V2 Performance API — shape matches frontend/src/types/signal.ts PerformanceStats.

Consolidates multiple `/api/analytics/*` reads into a single authenticated
GET so the Performance.tsx page hydrates from one round-trip.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.routes.auth import get_current_user
from app.api.signal_mapper import derive_category
from app.db.database import get_db_session
from app.db.models import (
    Event,
    Order,
    Portfolio,
    Position,
    Signal,
    SignalOutcome,
    UserProfile,
)


router = APIRouter(prefix="/performance", tags=["performance"])


# ── Wire shapes (match `PerformanceStats` on the client) ─────────────
class CategoryDistribution(BaseModel):
    category: str
    count: int
    percentage: int


class UserCategoryWinRate(BaseModel):
    category: str
    winRate: float
    signalCount: int


class WinRatePoint(BaseModel):
    date: str
    platform: float
    user: float


class GainsOverTimePoint(BaseModel):
    week: str
    gain: float


class PerformanceStatsOut(BaseModel):
    userSignalsFollowed: int
    userCorrectPredictions: int
    userWinRate: float
    userBestCategory: str
    userBestCategoryWinRate: float
    userEstimatedGain: float
    userWinRateByCategory: list[UserCategoryWinRate]

    telegramAlertsReceived: int = 0
    telegramAlertsFollowed: int = 0
    telegramFollowRate: float = 0.0

    totalSignalsGenerated: int
    platformWinRate: float
    platformAvgScore: float
    avgPipelineDelay: int

    signalsByCategory: list[CategoryDistribution]
    winRateOverTime: list[WinRatePoint]
    gainsOverTime: list[GainsOverTimePoint]


# ── Helpers ──────────────────────────────────────────────────────────
_FR_CATEGORY_NAMES = {
    "geopolitics": "Géopolitique",
    "politics": "Politique",
    "economics": "Économie",
    "crypto": "Crypto",
    "sports": "Sport",
    "science": "Science",
}


def _week_key(dt: datetime) -> str:
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


# ── Endpoint ─────────────────────────────────────────────────────────
@router.get("/me", response_model=PerformanceStatsOut)
async def get_performance_me(
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    # ── Platform-wide metrics (not user-specific) ────────────────────
    total_signals = (await db.execute(select(func.count()).select_from(Signal))).scalar() or 0
    avg_score_raw = (
        await db.execute(select(func.avg(Signal.signal_score)))
    ).scalar()
    platform_avg_score = float(avg_score_raw or 0.0)

    resolved_total = (
        await db.execute(
            select(func.count())
            .select_from(SignalOutcome)
            .where(SignalOutcome.direction_correct.is_not(None))
        )
    ).scalar() or 0
    resolved_wins = (
        await db.execute(
            select(func.count())
            .select_from(SignalOutcome)
            .where(SignalOutcome.direction_correct.is_(True))
        )
    ).scalar() or 0
    platform_win_rate = (resolved_wins / resolved_total) if resolved_total else 0.0

    # Signals by category — aggregate on Event.bucket and normalise.
    bucket_rows = (
        await db.execute(
            select(Event.bucket, func.count(Signal.id))
            .join(Signal, Signal.event_id == Event.id)
            .group_by(Event.bucket)
        )
    ).all()
    cat_counts: dict[str, int] = {}
    for bucket, count in bucket_rows:
        cat, _label = derive_category(bucket, None, None)
        fr = _FR_CATEGORY_NAMES.get(cat, cat)
        cat_counts[fr] = cat_counts.get(fr, 0) + int(count or 0)
    total_cat = sum(cat_counts.values()) or 1
    signals_by_category = [
        CategoryDistribution(
            category=k,
            count=v,
            percentage=int(round(v / total_cat * 100)),
        )
        for k, v in sorted(cat_counts.items(), key=lambda kv: -kv[1])
    ]

    # ── User-specific metrics ────────────────────────────────────────
    pf_q = select(Portfolio).where(Portfolio.user_id == user.id).limit(1)
    portfolio = (await db.execute(pf_q)).scalar_one_or_none()

    signals_followed = 0
    correct_predictions = 0
    gain_by_week: dict[str, float] = defaultdict(float)
    per_category: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "correct": 0})
    user_estimated_gain = 0.0

    if portfolio is not None:
        # Orders -> signal_ids for this user.
        orders_q = (
            select(Order.signal_id, Order.market_id, Order.created_at)
            .where(
                Order.portfolio_id == portfolio.id,
                Order.signal_id.is_not(None),
            )
            .order_by(desc(Order.created_at))
        )
        signal_to_open_date: dict[int, datetime] = {}
        for sid, _mid, created in (await db.execute(orders_q)).all():
            if sid is None:
                continue
            signal_to_open_date.setdefault(int(sid), created)

        if signal_to_open_date:
            sig_q = (
                select(Signal)
                .options(
                    selectinload(Signal.event),
                    selectinload(Signal.outcome),
                )
                .where(Signal.id.in_(list(signal_to_open_date.keys())))
            )
            for sig in (await db.execute(sig_q)).scalars().all():
                signals_followed += 1
                bucket = sig.event.bucket if sig.event else None
                cat, _ = derive_category(
                    bucket,
                    sig.market.question if sig.market else None,
                    sig.event.event_title if sig.event else None,
                )
                fr = _FR_CATEGORY_NAMES.get(cat, cat)
                per_category[fr]["total"] += 1
                if sig.outcome and sig.outcome.direction_correct is True:
                    correct_predictions += 1
                    per_category[fr]["correct"] += 1

        # User gains from positions (same formula as L4).
        pos_q = (
            select(Position)
            .where(Position.portfolio_id == portfolio.id)
        )
        for pos in (await db.execute(pos_q)).scalars().all():
            entry = float(pos.entry_price)
            current = float(pos.current_price) if pos.current_price is not None else entry
            side_up = pos.side.upper()
            dir_factor = 1.0 if "YES" in side_up else -1.0
            pps = (current - entry) * dir_factor
            gain = pps * float(pos.size)
            user_estimated_gain += gain
            gain_by_week[_week_key(pos.opened_at)] += gain

    user_win_rate = (correct_predictions / signals_followed) if signals_followed else 0.0

    user_win_rate_by_category = [
        UserCategoryWinRate(
            category=cat_name,
            winRate=(data["correct"] / data["total"]) if data["total"] else 0.0,
            signalCount=data["total"],
        )
        for cat_name, data in sorted(
            per_category.items(),
            key=lambda kv: -kv[1]["total"],
        )
    ]

    # Best category: highest winRate with >=2 signals; fallback to any.
    best: Optional[UserCategoryWinRate] = None
    for entry in user_win_rate_by_category:
        if entry.signalCount < 2:
            continue
        if best is None or entry.winRate > best.winRate:
            best = entry
    if best is None and user_win_rate_by_category:
        best = max(user_win_rate_by_category, key=lambda c: c.winRate)

    # Weekly gains over the trailing 8 weeks — aligned with client's S-7..S-1
    # visual but using ISO week labels the UI can format itself.
    now_week = _week_key(datetime.now(timezone.utc))
    # Sort week keys
    weekly_gains = [
        GainsOverTimePoint(week=k, gain=round(v, 2))
        for k, v in sorted(gain_by_week.items())
    ]

    # Win-rate over time — weekly platform vs user. MVP returns a single
    # point (cumulative to date) so the chart still renders without
    # gimmicks; L10+ can backfill from DB.
    today = datetime.now(timezone.utc).date().isoformat()
    win_rate_over_time = [
        WinRatePoint(
            date=today,
            platform=round(platform_win_rate, 4),
            user=round(user_win_rate, 4),
        )
    ]
    _ = now_week  # anchor for future weekly backfill

    return PerformanceStatsOut(
        userSignalsFollowed=signals_followed,
        userCorrectPredictions=correct_predictions,
        userWinRate=round(user_win_rate, 4),
        userBestCategory=best.category if best else "—",
        userBestCategoryWinRate=best.winRate if best else 0.0,
        userEstimatedGain=round(user_estimated_gain, 2),
        userWinRateByCategory=user_win_rate_by_category,
        totalSignalsGenerated=int(total_signals),
        platformWinRate=round(platform_win_rate, 4),
        platformAvgScore=round(platform_avg_score, 1),
        avgPipelineDelay=0,
        signalsByCategory=signals_by_category,
        winRateOverTime=win_rate_over_time,
        gainsOverTime=weekly_gains,
    )
