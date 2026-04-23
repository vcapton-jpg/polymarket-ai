"""Integration tests for /api/trading/trade UserLimits gating."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.db.models import Market, OnboardingProgress, UserLimits


async def _setup_market(async_db_factory, market_id: str):
    async with async_db_factory() as s:
        s.add(Market(
            market_id=market_id,
            question="Test market",
            active=True,
            clob_token_ids={"yes": "1", "no": "2"},
            last_trade_price=0.5,
        ))
        await s.commit()


@pytest.mark.asyncio
async def test_trade_rejected_when_quiz_not_passed(async_db_factory, auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    market_id = "0xtest-quiz"
    auth_headers_for_user.markets_to_cleanup.append(market_id)
    await _setup_market(async_db_factory, market_id)

    async with async_db_factory() as s:
        s.add(UserLimits(user_id=uid, age_confirmed_18=True, quiz_passed=False))
        s.add(OnboardingProgress(user_id=uid, tutorial_done=True, budget_done=True))
        await s.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/api/trading/trade",
            headers=headers,
            json={
                "market_id": market_id,
                "direction": "BUY_YES",
                "amount": 5,
                "price": 0.5,
            },
        )

    assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"
    body = r.json()
    assert body["detail"]["reason"] == "quiz_not_passed"


@pytest.mark.asyncio
async def test_trade_rejected_over_weekly_budget(async_db_factory, auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    market_id = "0xtest-budget"
    auth_headers_for_user.markets_to_cleanup.append(market_id)
    await _setup_market(async_db_factory, market_id)

    async with async_db_factory() as s:
        s.add(UserLimits(
            user_id=uid,
            age_confirmed_18=True,
            quiz_passed=True,
            budget_weekly_eur=Decimal("20.00"),
            week_spent_eur=Decimal("18.00"),
            max_stake_eur=Decimal("10.00"),
        ))
        s.add(OnboardingProgress(user_id=uid, tutorial_done=True, budget_done=True))
        await s.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/api/trading/trade",
            headers=headers,
            json={
                "market_id": market_id,
                "direction": "BUY_YES",
                "amount": 5,
                "price": 0.5,
            },
        )

    assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"
    assert r.json()["detail"]["reason"] == "over_weekly_budget"
