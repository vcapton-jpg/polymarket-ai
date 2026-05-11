"""V2 Portfolio API — shape matches frontend/src/types/signal.ts Position.

The V2 UI expects remote-native positions (recorded via /api/trading/trade)
merged client-side with a localStorage bucket of manually-entered positions.
This endpoint owns the remote side. The DB Position has no direct
Signal FK — we infer the signal via the most recent Order that carried
a signal_id for the same (portfolio, market_id).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.routes.auth import get_current_user
from app.api.schemas_v2 import SignalCardOut
from app.api.signal_mapper import derive_direction, to_signal_card
from app.db.database import get_db_session
from app.db.models import (
    Event,
    EventNewsLink,
    NewsClean,
    Order,
    Portfolio,
    Position,
    Signal,
    UserProfile,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


# ── Shapes ───────────────────────────────────────────────────────────
class PositionV2Out(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    signalId: str
    signal: SignalCardOut
    direction: Literal["YES", "NO"]
    entryPrice: float
    currentPrice: float
    entryDate: datetime
    status: Literal["tenir", "surveiller", "vendre"]
    lifePercent: int
    estimatedGain: float
    stake: float
    resolved: bool
    correctPrediction: bool | None = None
    source: Literal["native"] = "native"


class PortfolioKpis(BaseModel):
    total_positions: int
    active_positions: int
    resolved_positions: int
    total_stake: float
    total_estimated_gain: float


class PortfolioV2Out(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    positions: list[PositionV2Out]
    resolved: list[PositionV2Out]
    kpis: PortfolioKpis


# ── Helpers ──────────────────────────────────────────────────────────
def _status_from_prices(
    side: str, entry: float, current: float | None
) -> Literal["tenir", "surveiller", "vendre"]:
    """Same 3-state heuristic the V2 UI uses. Direction-aware — NO positions
    win when the YES price drops.
    """
    if current is None:
        return "tenir"
    dir_ = derive_direction(side)
    delta = (current - entry) if dir_ == "YES" else (entry - current)
    if delta >= 0.08:
        return "vendre"
    if delta <= -0.08:
        return "surveiller"
    return "tenir"


def _life_percent(opened_at: datetime, horizon_days: int = 30) -> int:
    if opened_at.tzinfo is None:
        opened_at = opened_at.replace(tzinfo=UTC)
    elapsed = max(0.0, (datetime.now(UTC) - opened_at).total_seconds() / 86_400.0)
    remaining = 1 - min(1.0, elapsed / horizon_days)
    return max(5, min(100, round(remaining * 100)))


def _estimated_gain(
    side: str, entry: float, current: float | None, size: float
) -> float:
    if current is None:
        return 0.0
    dir_ = derive_direction(side)
    pps = (current - entry) if dir_ == "YES" else (entry - current)
    return round(pps * size, 2)


# ── Endpoint ─────────────────────────────────────────────────────────
@router.get("", response_model=PortfolioV2Out)
async def get_portfolio(
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    # Find (or lazily create) the user's main portfolio.
    pf_q = (
        select(Portfolio)
        .options(
            selectinload(Portfolio.positions).selectinload(Position.market),
        )
        .where(Portfolio.user_id == user.id)
        .limit(1)
    )
    portfolio = (await db.execute(pf_q)).scalar_one_or_none()
    if portfolio is None:
        # Empty payload for brand-new users — no 404 so the UI renders
        # the empty state cleanly.
        return PortfolioV2Out(
            positions=[],
            resolved=[],
            kpis=PortfolioKpis(
                total_positions=0,
                active_positions=0,
                resolved_positions=0,
                total_stake=0.0,
                total_estimated_gain=0.0,
            ),
        )

    # One map: market_id -> most recent Order.signal_id (where not null).
    orders_q = (
        select(Order.market_id, Order.signal_id, Order.created_at)
        .where(
            Order.portfolio_id == portfolio.id,
            Order.signal_id.is_not(None),
        )
        .order_by(desc(Order.created_at))
    )
    market_to_signal: dict[str, int] = {}
    for market_id, signal_id, _ in (await db.execute(orders_q)).all():
        if market_id not in market_to_signal and signal_id is not None:
            market_to_signal[market_id] = int(signal_id)

    signal_ids = set(market_to_signal.values())
    signal_cache: dict[int, Signal] = {}
    if signal_ids:
        sig_q = (
            select(Signal)
            .options(
                selectinload(Signal.event).selectinload(Event.news_links)
                .selectinload(EventNewsLink.news_clean)
                .selectinload(NewsClean.news),
                selectinload(Signal.market),
            )
            .where(Signal.id.in_(signal_ids))
        )
        for s in (await db.execute(sig_q)).scalars().all():
            signal_cache[s.id] = s

    active: list[PositionV2Out] = []
    resolved: list[PositionV2Out] = []
    total_stake = 0.0
    total_gain = 0.0

    for pos in portfolio.positions:
        signal_id = market_to_signal.get(pos.market_id)
        signal = signal_cache.get(signal_id) if signal_id else None
        if signal is None:
            # Orphaned position (no order -> signal ref). Skip in V2 UI.
            continue

        entry = float(pos.entry_price)
        current = float(pos.current_price) if pos.current_price is not None else None
        stake_usd = float(pos.size) * entry
        gain = _estimated_gain(pos.side, entry, current, float(pos.size))
        total_stake += stake_usd
        total_gain += gain

        is_resolved = pos.status.lower() in ("closed", "resolved", "filled_final")

        payload = PositionV2Out(
            id=str(pos.id),
            signalId=str(signal.id),
            signal=to_signal_card(signal),
            direction=derive_direction(pos.side),
            entryPrice=entry,
            currentPrice=current if current is not None else entry,
            entryDate=pos.opened_at,
            status=_status_from_prices(pos.side, entry, current),
            lifePercent=_life_percent(pos.opened_at),
            estimatedGain=gain,
            stake=round(stake_usd, 2),
            resolved=is_resolved,
            correctPrediction=(gain > 0) if is_resolved else None,
        )
        (resolved if is_resolved else active).append(payload)

    return PortfolioV2Out(
        positions=active,
        resolved=resolved,
        kpis=PortfolioKpis(
            total_positions=len(active) + len(resolved),
            active_positions=len(active),
            resolved_positions=len(resolved),
            total_stake=round(total_stake, 2),
            total_estimated_gain=round(total_gain, 2),
        ),
    )
