"""B2B API routes — external signal consumption for third-party builders."""

import hashlib
import logging
from datetime import UTC

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db_session
from app.db.models import ApiKeyB2B, Signal, SignalOutcome

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["b2b"])


async def verify_b2b_key(
    x_api_key: str | None = Header(None),
    db: AsyncSession = Depends(get_db_session),
) -> ApiKeyB2B:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-Api-Key header required")

    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    result = await db.execute(
        select(ApiKeyB2B).where(ApiKeyB2B.key_hash == key_hash, ApiKeyB2B.active.is_(True))
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return api_key


@router.get("/signals")
async def b2b_signals(
    bucket: str | None = Query(None),
    min_score: int = Query(60),
    limit: int = Query(50, le=200),
    api_key: ApiKeyB2B = Depends(verify_b2b_key),
    db: AsyncSession = Depends(get_db_session),
):
    """Get latest signals (B2B endpoint)."""
    query = select(Signal).where(Signal.signal_score >= min_score)
    if bucket:
        from app.db.models import Event
        query = query.join(Event, Signal.event_id == Event.id).where(Event.bucket == bucket)
    query = query.order_by(desc(Signal.created_at)).limit(limit)

    result = await db.execute(query)
    signals = result.scalars().all()

    return {
        "signals": [
            {
                "id": s.id,
                "event_id": s.event_id,
                "market_id": s.market_id,
                "signal_score": float(s.signal_score),
                "signal_strength": float(s.signal_strength) if s.signal_strength else None,
                "trade_quality": float(s.trade_quality) if s.trade_quality else None,
                "direction": s.direction,
                "confidence": s.confidence_label,
                "market_price": float(s.market_price_at_signal) if s.market_price_at_signal else None,
                "created_at": s.created_at.isoformat(),
            }
            for s in signals
        ],
        "count": len(signals),
        "tier": api_key.tier,
    }


@router.get("/signals/{signal_id}")
async def b2b_signal_detail(
    signal_id: int,
    api_key: ApiKeyB2B = Depends(verify_b2b_key),
    db: AsyncSession = Depends(get_db_session),
):
    """Get signal detail with outcome (B2B endpoint)."""
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    outcome_result = await db.execute(
        select(SignalOutcome).where(SignalOutcome.signal_id == signal_id)
    )
    outcome = outcome_result.scalar_one_or_none()

    return {
        "id": signal.id,
        "event_id": signal.event_id,
        "market_id": signal.market_id,
        "signal_score": float(signal.signal_score),
        "signal_strength": float(signal.signal_strength) if signal.signal_strength else None,
        "trade_quality": float(signal.trade_quality) if signal.trade_quality else None,
        "direction": signal.direction,
        "confidence": signal.confidence_label,
        "urgency": signal.urgency_label,
        "market_price": float(signal.market_price_at_signal) if signal.market_price_at_signal else None,
        "created_at": signal.created_at.isoformat(),
        "outcome": {
            "direction_correct": outcome.direction_correct,
            "price_t1h": float(outcome.price_t1h) if outcome.price_t1h else None,
            "price_t24h": float(outcome.price_t24h) if outcome.price_t24h else None,
            "move_t1h_pct": float(outcome.move_t1h_pct) if outcome.move_t1h_pct else None,
        } if outcome else None,
    }


@router.get("/historical")
async def b2b_historical(
    days: int = Query(30, le=90),
    api_key: ApiKeyB2B = Depends(verify_b2b_key),
    db: AsyncSession = Depends(get_db_session),
):
    """Get historical signal performance (B2B endpoint)."""
    if api_key.tier not in ("pro", "enterprise"):
        raise HTTPException(status_code=403, detail="Historical data requires pro or enterprise tier")

    from datetime import datetime, timedelta
    cutoff = datetime.now(UTC) - timedelta(days=days)

    result = await db.execute(
        select(Signal).where(Signal.created_at >= cutoff).order_by(desc(Signal.created_at))
    )
    signals = result.scalars().all()

    outcome_result = await db.execute(
        select(SignalOutcome)
        .join(Signal)
        .where(Signal.created_at >= cutoff, SignalOutcome.direction_correct.is_not(None))
    )
    outcomes = outcome_result.scalars().all()
    wins = sum(1 for o in outcomes if o.direction_correct)

    return {
        "period_days": days,
        "total_signals": len(signals),
        "resolved": len(outcomes),
        "wins": wins,
        "losses": len(outcomes) - wins,
        "win_rate": round(wins / len(outcomes) * 100, 1) if outcomes else None,
    }
