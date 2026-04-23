"""Learn & Trade SQLAlchemy models — insert/defaults smoke tests.

Wraps each insert with parent-row setup (UserProfile, Market) and FK-safe
teardown so the test DB stays clean across runs. Uses high user_ids
(999001+) to avoid clashing with real data.

Creates a fresh async engine per test (cf. test_migration_019) to avoid
event-loop conflicts with the module-level session factory cache.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models import (
    Market,
    OnboardingProgress,  # noqa: F401 — import exercised as part of the model surface
    OutcomeView,  # noqa: F401 — import exercised as part of the model surface
    PaperPosition,
    QuizAttempt,  # noqa: F401 — import exercised as part of the model surface
    UserLimits,
    UserProfile,
)


def _fresh_factory():
    """Build an engine + session factory bound to the current event loop.

    Prevents asyncpg "Future attached to a different loop" errors when
    multiple @pytest.mark.asyncio tests run sequentially in one session.
    """
    engine = create_async_engine(get_settings().database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


@pytest.mark.asyncio
async def test_user_limits_defaults_and_insert():
    engine, factory = _fresh_factory()
    user_id = 999001
    try:
        # Seed parent UserProfile so FK user_limits.user_id -> user_profiles.id holds.
        async with factory() as s:
            s.add(UserProfile(id=user_id, email="learn-trade-test-999001@example.com"))
            await s.commit()

        try:
            async with factory() as s:
                row = UserLimits(user_id=user_id)
                s.add(row)
                await s.commit()
                await s.refresh(row)

                assert int(row.budget_weekly_eur) == 20
                assert int(row.max_stake_eur) == 10
                assert row.level == 1
                assert row.quiz_passed is False
                assert row.age_confirmed_18 is False
        finally:
            # UserLimits cascade-deletes via UserProfile delete.
            async with factory() as s:
                await s.execute(delete(UserLimits).where(UserLimits.user_id == user_id))
                await s.execute(delete(UserProfile).where(UserProfile.id == user_id))
                await s.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_paper_position_tutorial_flag():
    engine, factory = _fresh_factory()
    user_id = 999002
    market_id = "m-learn-trade-test-999002"
    try:
        # Seed parents — paper_positions FKs to user_profiles.id and markets.market_id.
        async with factory() as s:
            s.add(UserProfile(id=user_id, email="learn-trade-test-999002@example.com"))
            s.add(Market(market_id=market_id, question="test market for paper position?"))
            await s.commit()

        try:
            async with factory() as s:
                pos = PaperPosition(
                    user_id=user_id,
                    market_id=market_id,
                    direction="YES",
                    stake_eur=5.0,
                    entry_price=0.42,
                    is_tutorial=True,
                )
                s.add(pos)
                await s.commit()
                await s.refresh(pos)

                assert pos.is_tutorial is True
                assert pos.resolved is False
        finally:
            async with factory() as s:
                await s.execute(delete(PaperPosition).where(PaperPosition.user_id == user_id))
                await s.execute(delete(Market).where(Market.market_id == market_id))
                await s.execute(delete(UserProfile).where(UserProfile.id == user_id))
                await s.commit()
    finally:
        await engine.dispose()
