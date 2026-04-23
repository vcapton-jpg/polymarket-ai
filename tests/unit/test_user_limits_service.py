"""UserLimits service tests — budget / cooloff / quiz gating.

Uses `async_db_factory` (per-test engine + session factory) and the autouse
`_reset_db_cache` fixture so the service's `get_session_factory()` call
rebuilds against the current pytest-asyncio event loop.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa

from app.db.models import OnboardingProgress, UserLimits, UserProfile
from app.services.user_limits import (
    TradeDecision,
    can_trade_real,
    register_trade_result,
)


async def _seed(factory, *, user_id, limits_kwargs=None, onb_kwargs=None):
    """Insert UserProfile parent + optional UserLimits + optional OnboardingProgress.

    Returns an async cleanup callable that deletes the three rows in FK order.
    """
    async with factory() as s:
        s.add(UserProfile(id=user_id, email=f"test{user_id}@example.com"))
        await s.commit()

        if limits_kwargs is not None:
            s.add(UserLimits(user_id=user_id, **limits_kwargs))
        if onb_kwargs is not None:
            s.add(OnboardingProgress(user_id=user_id, **onb_kwargs))
        if limits_kwargs is not None or onb_kwargs is not None:
            await s.commit()

    async def _cleanup():
        async with factory() as s:
            await s.execute(
                sa.delete(OnboardingProgress).where(OnboardingProgress.user_id == user_id)
            )
            await s.execute(sa.delete(UserLimits).where(UserLimits.user_id == user_id))
            await s.execute(sa.delete(UserProfile).where(UserProfile.id == user_id))
            await s.commit()

    return _cleanup


@pytest.mark.asyncio
async def test_cannot_trade_if_quiz_not_passed(async_db_factory):
    user_id = 900001
    cleanup = await _seed(
        async_db_factory,
        user_id=user_id,
        limits_kwargs={"quiz_passed": False, "age_confirmed_18": True},
        onb_kwargs={"tutorial_done": True, "quiz_done": False, "budget_done": True},
    )
    try:
        decision = await can_trade_real(user_id=user_id, stake_eur=5)
        assert isinstance(decision, TradeDecision)
        assert decision.allowed is False
        assert decision.reason == "quiz_not_passed"
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_cannot_trade_if_over_weekly_budget(async_db_factory):
    user_id = 900002
    cleanup = await _seed(
        async_db_factory,
        user_id=user_id,
        limits_kwargs={
            "quiz_passed": True,
            "age_confirmed_18": True,
            "budget_weekly_eur": 20,
            "week_spent_eur": 18,
        },
        onb_kwargs={"tutorial_done": True, "quiz_done": True, "budget_done": True},
    )
    try:
        decision = await can_trade_real(user_id=user_id, stake_eur=5)
        assert decision.allowed is False
        assert decision.reason == "over_weekly_budget"
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_cannot_trade_if_over_max_stake(async_db_factory):
    user_id = 900003
    cleanup = await _seed(
        async_db_factory,
        user_id=user_id,
        limits_kwargs={
            "quiz_passed": True,
            "age_confirmed_18": True,
            "max_stake_eur": 10,
        },
        onb_kwargs={"tutorial_done": True, "quiz_done": True, "budget_done": True},
    )
    try:
        decision = await can_trade_real(user_id=user_id, stake_eur=15)
        assert decision.allowed is False
        assert decision.reason == "over_max_stake"
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_cannot_trade_if_in_cooloff(async_db_factory):
    user_id = 900004
    cooloff_until = datetime.now(timezone.utc) + timedelta(hours=12)
    cleanup = await _seed(
        async_db_factory,
        user_id=user_id,
        limits_kwargs={
            "quiz_passed": True,
            "age_confirmed_18": True,
            "cooloff_until": cooloff_until,
        },
        onb_kwargs={"tutorial_done": True, "quiz_done": True, "budget_done": True},
    )
    try:
        decision = await can_trade_real(user_id=user_id, stake_eur=5)
        assert decision.allowed is False
        assert decision.reason == "in_cooloff"
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_register_loss_increments_consecutive_losses(async_db_factory):
    user_id = 900005
    cleanup = await _seed(
        async_db_factory,
        user_id=user_id,
        limits_kwargs={"consecutive_losses": 0},
        onb_kwargs=None,
    )
    try:
        await register_trade_result(user_id=user_id, won=False, stake_eur=5)
        async with async_db_factory() as s:
            row = await s.get(UserLimits, user_id)
            assert row is not None
            assert row.consecutive_losses == 1
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_three_losses_triggers_cooloff(async_db_factory):
    user_id = 900006
    cleanup = await _seed(
        async_db_factory,
        user_id=user_id,
        limits_kwargs={"consecutive_losses": 2},
        onb_kwargs=None,
    )
    try:
        before = datetime.now(timezone.utc)
        await register_trade_result(user_id=user_id, won=False, stake_eur=5)
        async with async_db_factory() as s:
            row = await s.get(UserLimits, user_id)
            assert row is not None
            assert row.consecutive_losses == 3
            assert row.cooloff_until is not None
            assert row.cooloff_until > before
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_win_resets_consecutive_losses(async_db_factory):
    user_id = 900007
    cleanup = await _seed(
        async_db_factory,
        user_id=user_id,
        limits_kwargs={"consecutive_losses": 2},
        onb_kwargs=None,
    )
    try:
        await register_trade_result(user_id=user_id, won=True, stake_eur=5)
        async with async_db_factory() as s:
            row = await s.get(UserLimits, user_id)
            assert row is not None
            assert row.consecutive_losses == 0
    finally:
        await cleanup()
