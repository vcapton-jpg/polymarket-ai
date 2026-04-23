"""E2E: _persist_signal writes one signal_articles row per article with variant='signal'."""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.db.models import (
    Event,
    EventNewsLink,
    Market,
    News,
    NewsClean,
    Signal,
    SignalArticle,
    SignalPrediction,
)


@pytest.fixture
async def _clean_up(async_db_factory):
    async def _wipe():
        async with async_db_factory() as s:
            sig_ids = (await s.execute(
                select(Signal.id).where(Signal.market_id == "0xproda")
            )).scalars().all()
            if sig_ids:
                await s.execute(delete(SignalArticle).where(SignalArticle.signal_id.in_(sig_ids)))
                await s.execute(delete(SignalPrediction).where(SignalPrediction.signal_id.in_(sig_ids)))
            await s.execute(delete(Signal).where(Signal.market_id == "0xproda"))
            await s.execute(delete(EventNewsLink).where(EventNewsLink.event_id == 801))
            await s.execute(delete(NewsClean).where(NewsClean.id.in_([8001, 8002])))
            await s.execute(delete(News).where(News.id.in_([88001, 88002])))
            await s.execute(delete(Event).where(Event.id == 801))
            await s.execute(delete(Market).where(Market.market_id == "0xproda"))
            await s.commit()
    await _wipe()
    yield
    await _wipe()


@pytest.mark.asyncio
async def test_persist_signal_writes_signal_articles_rows(async_db_factory, _clean_up):
    from app.signal.signal_builder import _persist_signal

    async with async_db_factory() as s:
        s.add(Market(market_id="0xproda", question="q", active=True))
        s.add(Event(id=801, event_title="e"))
        await s.flush()
        for (nid, cid) in [(88001, 8001), (88002, 8002)]:
            s.add(News(id=nid, url=f"https://x/{nid}", title="t", text="b",
                       source_name="src", source_tier=1, source_weight=0.5))
            s.add(NewsClean(id=cid, news_id=nid, clean_text=f"c-{cid}"))
            s.add(EventNewsLink(event_id=801, clean_id=cid))
        await s.commit()

    assembled = {
        "event_id": 801,
        "market_id": "0xproda",
        "market_price": 0.65,
        "reasoning": "because reasons",
        "llm_model_version": "gpt-4o-test",
        "source_tier_mix": {"tier1": 2},
        "direction_recommendation": "YES",
        "impact_score": 0.8,
        "confidence": 0.7,
        "article_excerpts": [
            {"news_clean_id": 8001, "excerpt": "quote A", "relevance": 0.9},
            {"news_clean_id": 8002, "excerpt": "quote B", "relevance": 0.8},
        ],
    }
    articles = [
        {"news_clean_id": 8001, "direction_hint": "YES", "source_weight": 0.9,
         "excerpt": "quote A"},
        {"news_clean_id": 8002, "direction_hint": "NO", "source_weight": 0.3,
         "excerpt": "quote B"},
    ]
    await _persist_signal(assembled, articles)

    async with async_db_factory() as s:
        sig = (await s.execute(
            select(Signal).where(Signal.market_id == "0xproda")
        )).scalar_one()
        rows = (await s.execute(
            select(SignalArticle).where(SignalArticle.signal_id == sig.id)
        )).scalars().all()
    assert {r.variant for r in rows} == {"signal"}
    assert {r.news_clean_id for r in rows} == {8001, 8002}
    assert sorted(r.rank for r in rows) == [1, 2]
