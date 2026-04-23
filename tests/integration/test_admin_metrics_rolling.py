from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.api.main import app
from app.core.config import get_settings
from app.db.models import Event, Market, Signal, SignalPrediction


@pytest.fixture
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_rolling_returns_per_day_series(
    async_db_factory, auth_headers_for_user, monkeypatch, _clear_settings_cache
):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@x.com")
    get_settings.cache_clear()

    _uid, headers = await auth_headers_for_user(email="admin@x.com")
    auth_headers_for_user.markets_to_cleanup.append("0xroll")

    now = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)

    # Pre-clean in case of prior failed run
    async with async_db_factory() as s_pre:
        await s_pre.execute(delete(SignalPrediction).where(SignalPrediction.signal_id.in_(
            select(Signal.id).where(Signal.event_id == 401)
        )))
        await s_pre.execute(delete(Signal).where(Signal.event_id == 401))
        await s_pre.execute(delete(Event).where(Event.id == 401))
        await s_pre.execute(delete(Market).where(Market.market_id == "0xroll"))
        await s_pre.commit()

    try:
        async with async_db_factory() as s:
            s.add(Market(market_id="0xroll", question="q", active=True))
            s.add(Event(id=401, event_title="e"))
            await s.flush()
            for d in (1, 2, 3):
                sig = Signal(
                    event_id=401, market_id="0xroll", signal_score=80,
                    direction="BUY_YES", market_price_at_signal=0.6,
                )
                s.add(sig)
                await s.flush()
                s.add(SignalPrediction(
                    signal_id=sig.id, variant="signal",
                    predicted_direction="BUY_YES", predicted_probability=0.7,
                    direction_correct=True,
                    created_at=now - timedelta(days=d),
                    resolved_at=now - timedelta(days=d) + timedelta(hours=1),
                ))
            await s.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            r = await c.get(
                "/api/admin/metrics/variants/rolling?window=30d&step=1d",
                headers=headers,
            )
        assert r.status_code == 200, r.text
        body = r.json()
        series = body["series"]
        sig_pts = [p for p in series if p["variant"] == "signal"]
        assert len(sig_pts) >= 3
        ns = [p["n_cumulative"] for p in sig_pts]
        assert ns == sorted(ns)
        assert max(ns) == 3
    finally:
        async with async_db_factory() as s2:
            await s2.execute(delete(SignalPrediction).where(SignalPrediction.signal_id.in_(
                select(Signal.id).where(Signal.event_id == 401)
            )))
            await s2.execute(delete(Signal).where(Signal.event_id == 401))
            await s2.execute(delete(Event).where(Event.id == 401))
            await s2.commit()
