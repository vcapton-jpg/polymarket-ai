"""End-to-end shadow test: the task writes the SignalPrediction + 5 SignalArticle rows."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from functools import partial

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models import (
    Event, EventNewsLink, Market, News, NewsClean,
    Signal, SignalArticle, SignalPrediction,
)


async def _run_task_in_thread(task, *args):
    """Run a synchronous Celery task in a thread executor.

    pytest-asyncio keeps a running event loop; `_run_async` (used by every
    Celery task body) calls `loop.run_until_complete()` on a *second* loop,
    which Python rejects with "Cannot run the event loop while another loop is
    running".  Offloading the `.apply()` call to a thread gives it a clean
    execution context with no running loop.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(task.apply, args=args))


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
                select(Signal.id).where(Signal.market_id == "0xshadow")
            )).scalars().all()
            if sig_ids:
                await s.execute(delete(SignalArticle).where(SignalArticle.signal_id.in_(sig_ids)))
                await s.execute(delete(SignalPrediction).where(SignalPrediction.signal_id.in_(sig_ids)))
            await s.execute(delete(Signal).where(Signal.market_id == "0xshadow"))
            await s.execute(delete(EventNewsLink).where(EventNewsLink.event_id == 910))
            await s.execute(delete(NewsClean).where(NewsClean.id.in_([6001, 6002, 6003, 6004, 6005])))
            await s.execute(delete(News).where(News.id.in_([66001, 66002, 66003, 66004, 66005])))
            await s.execute(delete(Event).where(Event.id == 910))
            await s.execute(delete(Market).where(Market.market_id == "0xshadow"))
            await s.commit()
    await _wipe()
    yield
    await _wipe()


class _FakeAnalyzer:
    model_version = "fake-v2"

    async def analyze(self, **_kwargs):
        return {
            "reasoning": "fake reasoning",
            "direction_recommendation": "YES",
            "impact_score": 0.7,
            "confidence": 0.6,
            "article_excerpts": [
                {"news_clean_id": 6001, "excerpt": "excerpt A", "relevance": 0.9},
            ],
            "source_tier_mix": {"tier1": 1},
        }


@pytest.mark.asyncio
async def test_shadow_rerun_writes_prediction_and_articles(
    async_db_factory, monkeypatch, _clear_settings_cache, _clean_up
):
    monkeypatch.setenv("SOURCING_SHADOW_ENABLED", "true")
    get_settings.cache_clear()

    # Seed: 1 market (with embedding), 1 event, 5 articles linked to event
    # all within 72h window.
    now = datetime.now(timezone.utc)
    async with async_db_factory() as s:
        s.add(Market(
            market_id="0xshadow", question="q", active=True,
            embedding=[0.1] * 1536,
        ))
        s.add(Event(id=910, event_title="e"))
        await s.flush()
        for i, (nid, cid, age) in enumerate([
            (66001, 6001, 1),
            (66002, 6002, 5),
            (66003, 6003, 10),
            (66004, 6004, 30),
            (66005, 6005, 60),
        ]):
            s.add(News(
                id=nid, url=f"https://x/{nid}", title=f"t-{nid}", text="b",
                source_name="src", source_tier=1, source_weight=0.5,
                publish_date=now - timedelta(hours=age),
            ))
            s.add(NewsClean(id=cid, news_id=nid, clean_text=f"c-{cid}",
                            embedding=[0.1] * 1536))
            s.add(EventNewsLink(event_id=910, clean_id=cid))
        sig = Signal(
            event_id=910, market_id="0xshadow", signal_score=80,
            direction="BUY_YES", market_price_at_signal=0.6,
        )
        s.add(sig)
        await s.commit()
        sid = sig.id

    # Monkeypatch the analyzer factory used inside the task
    import app.workers.tasks_sourcing as ts_mod
    monkeypatch.setattr(ts_mod, "create_reasoning_analyzer", lambda: _FakeAnalyzer())

    # Run the task in eager mode (via thread to avoid nested-loop error in pytest-asyncio)
    from app.workers.celery_app import celery_app
    from app.workers.tasks_sourcing import sourcing_shadow_rerun
    celery_app.conf.task_always_eager = True
    try:
        await _run_task_in_thread(sourcing_shadow_rerun, sid)
    finally:
        celery_app.conf.task_always_eager = False

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

    assert len(preds) == 1
    assert preds[0].predicted_direction == "BUY_YES"
    assert float(preds[0].predicted_probability) == pytest.approx(0.7, abs=1e-4)
    assert len(arts) == 5   # top_k default
    assert {a.rank for a in arts} == {1, 2, 3, 4, 5}


@pytest.mark.asyncio
async def test_shadow_rerun_is_idempotent(
    async_db_factory, monkeypatch, _clear_settings_cache, _clean_up
):
    monkeypatch.setenv("SOURCING_SHADOW_ENABLED", "true")
    get_settings.cache_clear()

    now = datetime.now(timezone.utc)
    async with async_db_factory() as s:
        s.add(Market(market_id="0xshadow", question="q", active=True,
                     embedding=[0.1] * 1536))
        s.add(Event(id=910, event_title="e"))
        await s.flush()
        s.add(News(id=66001, url="https://x/1", title="t", text="b",
                   source_name="src", source_tier=1, source_weight=0.5,
                   publish_date=now - timedelta(hours=1)))
        s.add(NewsClean(id=6001, news_id=66001, clean_text="c",
                        embedding=[0.1] * 1536))
        s.add(EventNewsLink(event_id=910, clean_id=6001))
        sig = Signal(
            event_id=910, market_id="0xshadow", signal_score=80,
            direction="BUY_YES", market_price_at_signal=0.6,
        )
        s.add(sig)
        await s.commit()
        sid = sig.id

    import app.workers.tasks_sourcing as ts_mod
    monkeypatch.setattr(ts_mod, "create_reasoning_analyzer", lambda: _FakeAnalyzer())

    from app.workers.celery_app import celery_app
    from app.workers.tasks_sourcing import sourcing_shadow_rerun
    celery_app.conf.task_always_eager = True
    try:
        await _run_task_in_thread(sourcing_shadow_rerun, sid)
        await _run_task_in_thread(sourcing_shadow_rerun, sid)  # second run
    finally:
        celery_app.conf.task_always_eager = False

    async with async_db_factory() as s:
        preds = (await s.execute(
            select(SignalPrediction).where(
                SignalPrediction.signal_id == sid,
                SignalPrediction.variant == "signal_v2_reranked",
            )
        )).scalars().all()
    # Second run must NOT create a second prediction row.
    assert len(preds) == 1
