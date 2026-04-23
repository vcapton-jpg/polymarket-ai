"""Unit test for register_user_outcome_for_signal hook (Task 8)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from app.db.models import UserLimits, UserProfile
from app.workers.tasks_outcomes import register_user_outcome_for_signal


@pytest.mark.asyncio
async def test_losing_signal_increments_consecutive_losses(async_db_factory):
    """When register_user_outcome_for_signal is invoked with won=False, the
    user's UserLimits.consecutive_losses increments by 1 and cooloff_until
    stays None (single loss, below 3-loss threshold)."""
    email = f"cooloff-test-{uuid.uuid4().hex[:8]}@example.com"
    # Seed UserProfile + UserLimits
    async with async_db_factory() as s:
        user = UserProfile(email=email, plan="free")
        s.add(user)
        await s.commit()
        await s.refresh(user)
        uid = user.id
        s.add(UserLimits(
            user_id=uid,
            consecutive_losses=0,
            quiz_passed=True,
            age_confirmed_18=True,
        ))
        await s.commit()

    try:
        await register_user_outcome_for_signal(user_id=uid, won=False, stake_eur=5.0)

        async with async_db_factory() as s:
            row = await s.get(UserLimits, uid)
            assert row is not None
            assert row.consecutive_losses == 1
            assert row.cooloff_until is None  # 1 loss, cooloff at 3
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(UserProfile).where(UserProfile.id == uid))
            await s.commit()


@pytest.mark.asyncio
async def test_winning_signal_resets_consecutive_losses(async_db_factory):
    """A won=True outcome must reset consecutive_losses to 0."""
    email = f"cooloff-win-{uuid.uuid4().hex[:8]}@example.com"
    async with async_db_factory() as s:
        user = UserProfile(email=email, plan="free")
        s.add(user)
        await s.commit()
        await s.refresh(user)
        uid = user.id
        s.add(UserLimits(
            user_id=uid,
            consecutive_losses=2,
            quiz_passed=True,
            age_confirmed_18=True,
        ))
        await s.commit()

    try:
        await register_user_outcome_for_signal(user_id=uid, won=True, stake_eur=5.0)

        async with async_db_factory() as s:
            row = await s.get(UserLimits, uid)
            assert row.consecutive_losses == 0
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(UserProfile).where(UserProfile.id == uid))
            await s.commit()
