"""Integration tests for /api/onboarding/* routes."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.db.models import OnboardingProgress, UserLimits


@pytest.mark.asyncio
async def test_get_onboarding_status_empty(auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/onboarding/status", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["tutorial_done"] is False
    assert data["quiz_done"] is False
    assert data["can_trade_real"] is False


@pytest.mark.asyncio
async def test_budget_setup_persists_and_unlocks(async_db_factory, auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    # Pre-seed: tutorial + quiz done, quiz_passed
    async with async_db_factory() as s:
        s.add(OnboardingProgress(user_id=uid, tutorial_done=True, quiz_done=True))
        s.add(UserLimits(user_id=uid, quiz_passed=True))
        await s.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/api/onboarding/budget",
            headers=headers,
            json={
                "budget_weekly_eur": 30.0,
                "max_stake_eur": 5.0,
                "age_confirmed_18": True,
                "cgu_accepted": True,
            },
        )
    assert r.status_code == 200, r.text

    async with async_db_factory() as s:
        limits = await s.get(UserLimits, uid)
        onb = await s.get(OnboardingProgress, uid)
    assert float(limits.budget_weekly_eur) == 30.0
    assert float(limits.max_stake_eur) == 5.0
    assert limits.age_confirmed_18 is True
    assert limits.cgu_accepted_at is not None
    assert onb.budget_done is True
    assert onb.unlocked_real_trading_at is not None


@pytest.mark.asyncio
async def test_budget_setup_rejects_if_age_not_confirmed(auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/api/onboarding/budget",
            headers=headers,
            json={
                "budget_weekly_eur": 30.0,
                "max_stake_eur": 5.0,
                "age_confirmed_18": False,
                "cgu_accepted": True,
            },
        )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "age_not_confirmed" in (detail if isinstance(detail, str) else str(detail))
