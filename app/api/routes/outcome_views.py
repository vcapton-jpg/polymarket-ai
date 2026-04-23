"""Track when a user views the outcome explainer for a signal."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select

from app.api.routes.auth import get_current_user
from app.db.database import get_session_factory
from app.db.models import OutcomeView, UserProfile

router = APIRouter(prefix="/signals", tags=["signals"])


@router.post("/{signal_id}/outcome/viewed", status_code=204)
async def mark_outcome_viewed(
    signal_id: int,
    user: UserProfile = Depends(get_current_user),
) -> Response:
    """Record that this user saw the outcome explainer for this signal.

    Idempotent — if a row already exists for (user_id, signal_id), do nothing.
    """
    factory = get_session_factory()
    async with factory() as s:
        existing = (
            await s.execute(
                select(OutcomeView).where(
                    OutcomeView.user_id == user.id,
                    OutcomeView.signal_id == signal_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            s.add(OutcomeView(user_id=user.id, signal_id=signal_id))
            await s.commit()
    return Response(status_code=204)
