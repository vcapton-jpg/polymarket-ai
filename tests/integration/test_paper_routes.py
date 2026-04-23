"""Integration tests for /api/paper/* routes."""

from __future__ import annotations
import pytest
from httpx import AsyncClient, ASGITransport
from app.api.main import app
from app.db.models import Market


async def _seed_market(async_db_factory, market_id: str):
    async with async_db_factory() as s:
        s.add(Market(market_id=market_id, question="paper test", active=True))
        await s.commit()


async def _cleanup_market(async_db_factory, market_id: str):
    from sqlalchemy import delete
    async with async_db_factory() as s:
        await s.execute(delete(Market).where(Market.market_id == market_id))
        await s.commit()


@pytest.mark.asyncio
async def test_open_paper_position(async_db_factory, auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    mkt = "0xpaper-1"
    await _seed_market(async_db_factory, mkt)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            r = await c.post("/api/paper/trade", headers=headers, json={
                "market_id": mkt, "signal_id": None, "direction": "YES",
                "stake_eur": 5.0, "entry_price": 0.4, "is_tutorial": True,
            })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["direction"] == "YES"
        assert data["stake_eur"] == 5.0
        assert data["is_tutorial"] is True
    finally:
        await _cleanup_market(async_db_factory, mkt)


@pytest.mark.asyncio
async def test_list_paper_positions(async_db_factory, auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    mkt = "0xpaper-2"
    await _seed_market(async_db_factory, mkt)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            await c.post("/api/paper/trade", headers=headers, json={
                "market_id": mkt, "direction": "NO",
                "stake_eur": 3.0, "entry_price": 0.7, "is_tutorial": False,
            })
            r = await c.get("/api/paper/positions", headers=headers)
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(p["market_id"] == mkt for p in items)
    finally:
        await _cleanup_market(async_db_factory, mkt)


@pytest.mark.asyncio
async def test_paper_trade_rejects_invalid_direction(auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post("/api/paper/trade", headers=headers, json={
            "market_id": "0xpaper-3", "direction": "MAYBE",
            "stake_eur": 5.0, "entry_price": 0.5,
        })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_tutorial_done_after_5_paper_trades(async_db_factory, auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    mkt = "0xpaper-tut"
    await _seed_market(async_db_factory, mkt)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            for i in range(5):
                r = await c.post("/api/paper/trade", headers=headers, json={
                    "market_id": mkt, "direction": "YES",
                    "stake_eur": 1.0, "entry_price": 0.5, "is_tutorial": True,
                })
                assert r.status_code == 200, r.text

        # Verify OnboardingProgress.tutorial_done = True after 5 tutorial trades
        from app.db.models import OnboardingProgress
        async with async_db_factory() as s:
            onb = await s.get(OnboardingProgress, uid)
            assert onb is not None, "OnboardingProgress row not created"
            assert onb.tutorial_done is True
            assert onb.tutorial_trades_count == 5
    finally:
        await _cleanup_market(async_db_factory, mkt)
