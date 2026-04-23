"""Backfill script — covers the one-off migration that creates UserLimits
+ OnboardingProgress rows for pre-pivot users.

Uses the per-test async factory + autouse `_reset_db_cache` fixture so
the script's internal `get_session_factory()` call rebuilds against the
active pytest-asyncio event loop.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import sqlalchemy as sa

from app.db.models import OnboardingProgress, UserLimits, UserProfile
from scripts.backfill_user_limits import backfill


async def _seed_users(factory, user_ids):
    async with factory() as s:
        for uid in user_ids:
            s.add(UserProfile(id=uid, email=f"bf{uid}@example.com"))
        await s.commit()

    async def _cleanup():
        async with factory() as s:
            await s.execute(
                sa.delete(OnboardingProgress).where(
                    OnboardingProgress.user_id.in_(user_ids)
                )
            )
            await s.execute(
                sa.delete(UserLimits).where(UserLimits.user_id.in_(user_ids))
            )
            await s.execute(
                sa.delete(UserProfile).where(UserProfile.id.in_(user_ids))
            )
            await s.commit()

    return _cleanup


@pytest.mark.asyncio
async def test_backfill_creates_rows_for_users_without_limits(async_db_factory):
    uids = [700_001, 700_002]
    cleanup = await _seed_users(async_db_factory, uids)
    try:
        created = await backfill(dry_run=False)
        assert created >= 2

        async with async_db_factory() as s:
            row_a = await s.get(UserLimits, 700_001)
            row_b = await s.get(UserLimits, 700_002)
            onb_a = await s.get(OnboardingProgress, 700_001)
            onb_b = await s.get(OnboardingProgress, 700_002)

        assert row_a is not None
        assert row_b is not None
        # Safe defaults — matches the pivot spec.
        assert row_a.budget_weekly_eur == Decimal("20.00")
        assert row_a.max_stake_eur == Decimal("10.00")
        # Force re-quiz + re-age-confirm before the next real trade.
        assert row_a.quiz_passed is False
        assert row_a.age_confirmed_18 is False
        # OnboardingProgress rows created too.
        assert onb_a is not None
        assert onb_b is not None
        assert onb_a.tutorial_done is False
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_backfill_is_idempotent(async_db_factory):
    uids = [700_101, 700_102]
    cleanup = await _seed_users(async_db_factory, uids)
    try:
        first = await backfill(dry_run=False)
        assert first >= 2
        # Second run should create zero — the set difference is empty.
        second = await backfill(dry_run=False)
        assert second == 0
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_backfill_dry_run_creates_nothing(async_db_factory):
    uids = [700_201]
    cleanup = await _seed_users(async_db_factory, uids)
    try:
        created = await backfill(dry_run=True)
        assert created == 0
        async with async_db_factory() as s:
            row = await s.get(UserLimits, 700_201)
        assert row is None
    finally:
        await cleanup()
