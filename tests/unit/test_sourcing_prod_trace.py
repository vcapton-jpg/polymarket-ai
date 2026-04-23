"""Unit tests for prod_trace — writes the 'signal' variant audit rows."""

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
)
from app.sourcing.prod_trace import record_prod_signal_articles


async def _seed_signal_with_articles(session, *, event_id: int, sig_id: int | None = None):
    session.add(Market(market_id="0xpt", question="q", active=True))
    session.add(Event(id=event_id, event_title="e"))
    await session.flush()
    sig = Signal(
        event_id=event_id, market_id="0xpt", signal_score=80,
        direction="BUY_YES", market_price_at_signal=0.6,
    )
    session.add(sig)
    await session.flush()
    # Two news/news_clean rows for audit
    for (nid, cid) in [(7001, 5001), (7002, 5002)]:
        session.add(News(id=nid, url=f"https://x/{nid}", title="t",
                         text="b", source_name="s", source_tier=1,
                         source_weight=0.5))
        session.add(NewsClean(id=cid, news_id=nid, clean_text=f"c-{cid}"))
        session.add(EventNewsLink(event_id=event_id, clean_id=cid))
    await session.flush()
    return sig.id


@pytest.fixture
async def _clean_up(async_db_factory):
    async def _wipe():
        async with async_db_factory() as s:
            await s.execute(delete(SignalArticle).where(SignalArticle.news_clean_id.in_([5001, 5002])))
            await s.execute(delete(Signal).where(Signal.event_id == 701))
            await s.execute(delete(EventNewsLink).where(EventNewsLink.event_id == 701))
            await s.execute(delete(NewsClean).where(NewsClean.id.in_([5001, 5002])))
            await s.execute(delete(News).where(News.id.in_([7001, 7002])))
            await s.execute(delete(Event).where(Event.id == 701))
            await s.execute(delete(Market).where(Market.market_id == "0xpt"))
            await s.commit()
    await _wipe()
    yield
    await _wipe()


@pytest.mark.asyncio
async def test_record_prod_writes_one_row_per_article(async_db_factory, _clean_up):
    async with async_db_factory() as s:
        sid = await _seed_signal_with_articles(s, event_id=701)
        articles = [
            {"news_clean_id": 5001, "excerpt": None},
            {"news_clean_id": 5002, "excerpt": "quoted phrase"},
        ]
        n = await record_prod_signal_articles(s, signal_id=sid, articles=articles)
        await s.commit()
        assert n == 2

    async with async_db_factory() as s:
        rows = (
            await s.execute(
                select(SignalArticle).where(SignalArticle.signal_id == sid)
            )
        ).scalars().all()
    assert len(rows) == 2
    assert {r.variant for r in rows} == {"signal"}
    assert {r.news_clean_id for r in rows} == {5001, 5002}
    # Ranks are 1-based and contiguous
    assert sorted(r.rank for r in rows) == [1, 2]
    # Excerpt preserved when present
    excerpts = {r.news_clean_id: r.excerpt for r in rows}
    assert excerpts[5002] == "quoted phrase"


@pytest.mark.asyncio
async def test_record_prod_is_idempotent(async_db_factory, _clean_up):
    """Second call with same args is a no-op — PK conflict resolved silently."""
    async with async_db_factory() as s:
        sid = await _seed_signal_with_articles(s, event_id=701)
        articles = [{"news_clean_id": 5001, "excerpt": None}]
        await record_prod_signal_articles(s, signal_id=sid, articles=articles)
        await s.commit()
        # second call
        await record_prod_signal_articles(s, signal_id=sid, articles=articles)
        await s.commit()

    async with async_db_factory() as s:
        rows = (
            await s.execute(
                select(SignalArticle).where(SignalArticle.signal_id == sid)
            )
        ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_record_prod_skips_articles_without_news_clean_id(async_db_factory, _clean_up):
    async with async_db_factory() as s:
        sid = await _seed_signal_with_articles(s, event_id=701)
        articles = [
            {"news_clean_id": 5001, "excerpt": None},
            {"excerpt": "orphan"},  # missing news_clean_id → must be skipped
        ]
        n = await record_prod_signal_articles(s, signal_id=sid, articles=articles)
        await s.commit()
        assert n == 1
