"""Onboarding routes — status + budget setup for the Learn & Trade flow."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.routes.auth import get_current_user  # NOT app.api.deps
from app.api.schemas.learn_and_trade import (
    BudgetSetupIn,
    OnboardingStatusOut,
    UserLimitsOut,
)
from app.db.database import get_session_factory
from app.db.models import OnboardingProgress, UserLimits, UserProfile

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/status", response_model=OnboardingStatusOut)
async def get_onboarding_status(
    user: UserProfile = Depends(get_current_user),
) -> OnboardingStatusOut:
    factory = get_session_factory()
    async with factory() as s:
        onb = await s.get(OnboardingProgress, user.id)
        limits = await s.get(UserLimits, user.id)

    if onb is None:
        return OnboardingStatusOut(
            profile_done=False,
            tutorial_trades_count=0,
            tutorial_done=False,
            quiz_done=False,
            budget_done=False,
            can_trade_real=False,
        )

    can_trade_real = bool(
        onb.tutorial_done
        and onb.quiz_done
        and onb.budget_done
        and limits is not None
        and limits.age_confirmed_18
        and limits.quiz_passed
    )

    return OnboardingStatusOut(
        profile_done=bool(onb.profile_done),
        tutorial_trades_count=int(onb.tutorial_trades_count or 0),
        tutorial_done=bool(onb.tutorial_done),
        quiz_done=bool(onb.quiz_done),
        budget_done=bool(onb.budget_done),
        can_trade_real=can_trade_real,
    )


@router.post("/budget", response_model=UserLimitsOut)
async def setup_budget(
    body: BudgetSetupIn,
    user: UserProfile = Depends(get_current_user),
) -> UserLimitsOut:
    if not body.age_confirmed_18:
        raise HTTPException(status_code=400, detail="age_not_confirmed")
    if not body.cgu_accepted:
        raise HTTPException(status_code=400, detail="cgu_not_accepted")
    if body.max_stake_eur > body.budget_weekly_eur:
        raise HTTPException(status_code=400, detail="max_stake_exceeds_weekly_budget")

    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    async with factory() as s:
        limits = await s.get(UserLimits, user.id)
        if limits is None:
            limits = UserLimits(user_id=user.id)
            s.add(limits)
        limits.budget_weekly_eur = body.budget_weekly_eur
        limits.max_stake_eur = body.max_stake_eur
        limits.age_confirmed_18 = True
        limits.cgu_accepted_at = now

        onb = await s.get(OnboardingProgress, user.id)
        if onb is None:
            onb = OnboardingProgress(user_id=user.id)
            s.add(onb)
        onb.budget_done = True
        if onb.tutorial_done and onb.quiz_done and limits.quiz_passed:
            onb.unlocked_real_trading_at = now

        await s.commit()
        await s.refresh(limits)

    return UserLimitsOut.model_validate(limits, from_attributes=True)
