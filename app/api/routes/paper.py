"""Paper trading routes — no real money, uses paper_positions table."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.routes.auth import get_current_user  # NOT app.api.deps
from app.api.schemas.learn_and_trade import (
    PaperPositionOut, PaperPositionsOut, PaperTradeIn,
)
from app.db.database import get_session_factory
from app.db.models import PaperPosition, UserProfile

router = APIRouter(prefix="/paper", tags=["paper"])


@router.post("/trade", response_model=PaperPositionOut)
async def open_paper_position(
    body: PaperTradeIn,
    user: UserProfile = Depends(get_current_user),
) -> PaperPositionOut:
    """Open a virtual position. Pure sandbox: no real money, no progress
    tracking. The legacy `is_tutorial` flag used to drive the L&T tutorial
    gate (5 trades unlocked real trading); since the gate was removed, the
    flag is now informational only — kept on the wire so the column stays
    populated for analytics and existing client builds keep deserialising.
    """
    factory = get_session_factory()
    async with factory() as s:
        pos = PaperPosition(
            user_id=user.id,
            signal_id=body.signal_id,
            market_id=body.market_id,
            direction=body.direction,
            stake_eur=body.stake_eur,
            entry_price=body.entry_price,
            is_tutorial=body.is_tutorial,
        )
        s.add(pos)
        await s.commit()
        await s.refresh(pos)

    return PaperPositionOut.model_validate(pos, from_attributes=True)


@router.get("/positions", response_model=PaperPositionsOut)
async def list_paper_positions(
    user: UserProfile = Depends(get_current_user),
) -> PaperPositionsOut:
    factory = get_session_factory()
    async with factory() as s:
        rows = (
            await s.execute(
                select(PaperPosition)
                .where(PaperPosition.user_id == user.id)
                .order_by(PaperPosition.opened_at.desc())
                .limit(100)
            )
        ).scalars().all()

    return PaperPositionsOut(
        items=[PaperPositionOut.model_validate(r, from_attributes=True) for r in rows]
    )
