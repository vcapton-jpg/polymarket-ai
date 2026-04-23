"""Kill-switch test: with SOURCING_SHADOW_ENABLED=false the task writes nothing."""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models import (
    Event, Market, Signal, SignalArticle, SignalPrediction,
)


@pytest.fixture
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def _clean_up(async_db_factory):
    async def _wipe():
        async with async_db_factory() as s:
            sig_ids = (await s.execute(
                select(Signal.id).where(Signal.market_id == "0xkill")
            )).scalars().all()
            if sig_ids:
                await s.execute(delete(SignalArticle).where(SignalArticle.signal_id.in_(sig_ids)))
                await s.execute(delete(SignalPrediction).where(SignalPrediction.signal_id.in_(sig_ids)))
            await s.execute(delete(Signal).where(Signal.market_id == "0xkill"))
            await s.execute(delete(Event).where(Event.id == 901))
            await s.execute(delete(Market).where(Market.market_id == "0xkill"))
            await s.commit()
    await _wipe()
    yield
    await _wipe()


@pytest.mark.asyncio
async def test_task_is_noop_when_disabled(
    async_db_factory, monkeypatch, _clear_settings_cache, _clean_up
):
    monkeypatch.setenv("SOURCING_SHADOW_ENABLED", "false")
    get_settings.cache_clear()

    # Seed a signal
    async with async_db_factory() as s:
        s.add(Market(market_id="0xkill", question="q", active=True))
        s.add(Event(id=901, event_title="e"))
        await s.flush()
        sig = Signal(
            event_id=901, market_id="0xkill", signal_score=80,
            direction="BUY_YES", market_price_at_signal=0.6,
        )
        s.add(sig)
        await s.commit()
        sid = sig.id

    # Invoke the task synchronously via Celery eager mode
    from app.workers.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    try:
        from app.workers.tasks_sourcing import sourcing_shadow_rerun
        sourcing_shadow_rerun.apply(args=(sid,))
    finally:
        celery_app.conf.task_always_eager = False

    # Nothing should have been written
    async with async_db_factory() as s:
        preds = (await s.execute(
            select(SignalPrediction).where(
                SignalPrediction.signal_id == sid,
                SignalPrediction.variant == "signal_v2_reranked",
            )
        )).scalars().all()
        arts = (await s.execute(
            select(SignalArticle).where(
                SignalArticle.signal_id == sid,
                SignalArticle.variant == "signal_v2_reranked",
            )
        )).scalars().all()
    assert preds == []
    assert arts == []
