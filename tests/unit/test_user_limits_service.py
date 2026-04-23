"""UserLimits service tests — budget / cooloff / quiz gating.

Uses `async_db_factory` (per-test engine + session factory) and the autouse
`_reset_db_cache` fixture so the service's `get_session_factory()` call
rebuilds against the current pytest-asyncio event loop.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

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


@pytest.mark.asyncio
async def test_register_trade_opened_debits_budget_and_counts(async_db_factory):
    user_id = 900010
    factory = async_db_factory
    async with factory() as s:
        s.add(UserProfile(id=user_id, email=f"test{user_id}@example.com"))
        await s.commit()
        s.add(UserLimits(
            user_id=user_id,
            budget_weekly_eur=Decimal("20.00"),
            week_spent_eur=Decimal("5.00"),
            real_trades_count=3,
        ))
        await s.commit()
    try:
        from app.services.user_limits import register_trade_opened
        await register_trade_opened(user_id=user_id, stake_eur=7.50)
        async with factory() as s:
            row = await s.get(UserLimits, user_id)
            assert row.week_spent_eur == Decimal("12.50")
            assert row.real_trades_count == 4
    finally:
        async with factory() as s:
            await s.execute(sa.delete(UserLimits).where(UserLimits.user_id == user_id))
            await s.execute(sa.delete(UserProfile).where(UserProfile.id == user_id))
            await s.commit()


@pytest.mark.asyncio
async def test_register_trade_opened_resets_week_after_7_days(async_db_factory):
    user_id = 900011
    factory = async_db_factory
    stale_week = datetime.now(timezone.utc) - timedelta(days=8)
    async with factory() as s:
        s.add(UserProfile(id=user_id, email=f"test{user_id}@example.com"))
        await s.commit()
        s.add(UserLimits(
            user_id=user_id,
            week_spent_eur=Decimal("18.00"),
            week_reset_at=stale_week,
        ))
        await s.commit()
    try:
        from app.services.user_limits import register_trade_opened
        await register_trade_opened(user_id=user_id, stake_eur=5.00)
        async with factory() as s:
            row = await s.get(UserLimits, user_id)
            # After reset: week_spent_eur should be 5.00 (just the new stake), not 23.00
            assert row.week_spent_eur == Decimal("5.00")
            assert row.week_reset_at > stale_week + timedelta(days=7)
    finally:
        async with factory() as s:
            await s.execute(sa.delete(UserLimits).where(UserLimits.user_id == user_id))
            await s.execute(sa.delete(UserProfile).where(UserProfile.id == user_id))
            await s.commit()


@pytest.mark.asyncio
async def test_over_weekly_budget_decision_populates_remaining(async_db_factory):
    """Covers float-precision regression: budget 20 - spent 17.80 - stake 2.20 should REJECT cleanly."""
    user_id = 900012
    factory = async_db_factory
    async with factory() as s:
        s.add(UserProfile(id=user_id, email=f"test{user_id}@example.com"))
        await s.commit()
        s.add(UserLimits(
            user_id=user_id, quiz_passed=True, age_confirmed_18=True,
            budget_weekly_eur=Decimal("20.00"), week_spent_eur=Decimal("17.80"),
        ))
        s.add(OnboardingProgress(user_id=user_id, tutorial_done=True, quiz_done=True, budget_done=True))
        await s.commit()
    try:
        decision = await can_trade_real(user_id=user_id, stake_eur=2.20)
        # 20.00 - 17.80 = 2.20 → stake equal to remaining should be ALLOWED (not > remaining)
        assert decision.allowed is True, f"Should allow exact-match stake, got reason={decision.reason}"
        assert decision.remaining_budget_eur == pytest.approx(0.0, abs=0.005)

        decision_over = await can_trade_real(user_id=user_id, stake_eur=2.21)
        assert decision_over.allowed is False
        assert decision_over.reason == "over_weekly_budget"
        assert decision_over.remaining_budget_eur == pytest.approx(2.20, abs=0.005)
    finally:
        async with factory() as s:
            await s.execute(sa.delete(OnboardingProgress).where(OnboardingProgress.user_id == user_id))
            await s.execute(sa.delete(UserLimits).where(UserLimits.user_id == user_id))
            await s.execute(sa.delete(UserProfile).where(UserProfile.id == user_id))
            await s.commit()
