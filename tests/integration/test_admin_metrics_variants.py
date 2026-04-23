from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.api.main import app
from app.core.config import get_settings
from app.db.models import Event, Market, Signal, SignalPrediction


@pytest.fixture
def _clear_settings_cache():
    """Required around any test that mutates ADMIN_EMAILS via monkeypatch."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_variants_endpoint_rejects_non_admin(auth_headers_for_user):
    _uid, headers = await auth_headers_for_user(email="plain@x.com")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/admin/metrics/variants?window=30d", headers=headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_variants_endpoint_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/admin/metrics/variants?window=30d")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_variants_endpoint_returns_aggregates(
    async_db_factory, auth_headers_for_user, monkeypatch, _clear_settings_cache
):
    """Seed 10 resolved predictions across 2 variants, verify winrate + Wilson CI."""
    monkeypatch.setenv("ADMIN_EMAILS", "admin@x.com")
    get_settings.cache_clear()  # re-read env

    _uid, headers = await auth_headers_for_user(email="admin@x.com")
    auth_headers_for_user.markets_to_cleanup.append("0xadm")

    now = datetime.now(timezone.utc)
    # Pre-clean any leftover rows from a previous failed run
    async with async_db_factory() as s_pre:
        await s_pre.execute(delete(SignalPrediction).where(SignalPrediction.signal_id.in_(
            select(Signal.id).where(Signal.event_id == 301)
        )))
        await s_pre.execute(delete(Signal).where(Signal.event_id == 301))
        await s_pre.execute(delete(Event).where(Event.id == 301))
        await s_pre.commit()
    try:
        async with async_db_factory() as s:
            s.add(Market(market_id="0xadm", question="q", active=True))
            s.add(Event(id=301, event_title="e"))
            await s.flush()
            for i in range(10):
                sig = Signal(
                    event_id=301, market_id="0xadm", signal_score=80,
                    direction="BUY_YES", market_price_at_signal=0.6,
                )
                s.add(sig)
                await s.flush()
                s.add(SignalPrediction(
                    signal_id=sig.id, variant="signal",
                    predicted_direction="BUY_YES", predicted_probability=0.7,
                    direction_correct=(i < 7), brier_score=(0.3 if i < 7 else 0.49),
                    simulated_pnl_eur=(3.0 if i < 7 else -6.0),
                    resolved_at=now - timedelta(days=1),
                ))
                s.add(SignalPrediction(
                    signal_id=sig.id, variant="baseline_market_price",
                    predicted_direction="BUY_YES", predicted_probability=0.6,
                    direction_correct=(i < 5), brier_score=(0.16 if i < 5 else 0.36),
                    simulated_pnl_eur=(4.0 if i < 5 else -6.0),
                    resolved_at=now - timedelta(days=1),
                ))
            await s.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            r = await c.get("/api/admin/metrics/variants?window=30d", headers=headers)

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["window"] == "30d"
        variants = {v["variant"]: v for v in body["variants"]}
        assert "signal" in variants
        assert "baseline_market_price" in variants

        sig_v = variants["signal"]
        assert sig_v["n"] == 10
        assert sig_v["winrate"] == pytest.approx(0.7, abs=1e-4)
        assert 0.0 <= sig_v["winrate_ci95_low"] <= sig_v["winrate"] <= sig_v["winrate_ci95_high"] <= 1.0
        assert sig_v["pnl_total_eur"] == pytest.approx(7 * 3.0 + 3 * -6.0, abs=1e-2)
    finally:
        async with async_db_factory() as s2:
            await s2.execute(delete(SignalPrediction).where(SignalPrediction.signal_id.in_(
                select(Signal.id).where(Signal.event_id == 301)
            )))
            await s2.execute(delete(Signal).where(Signal.event_id == 301))
            await s2.execute(delete(Event).where(Event.id == 301))
            await s2.commit()
