"""Integration-ish unit tests for pool_builder — uses async_db_factory."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.models import Event, EventNewsLink, News, NewsClean
from app.sourcing.pool_builder import fetch_candidate_articles


T0 = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)


async def _seed_article(
    session,
    *,
    clean_id: int,
    news_id: int,
    event_id: int,
    age_hours: float,
    embedding: list[float] | None,
):
    session.add(News(
        id=news_id,
        url=f"https://x/{news_id}",
        title=f"t-{news_id}",
        text="body",
        source_name="src",
        source_tier=1,
        source_weight=0.5,
        publish_date=T0 - timedelta(hours=age_hours),
    ))
    session.add(NewsClean(
        id=clean_id,
        news_id=news_id,
        clean_text=f"clean-{clean_id}",
        embedding=embedding,
    ))
    await session.flush()
    session.add(EventNewsLink(event_id=event_id, clean_id=clean_id))


@pytest.fixture
async def _clean_up(async_db_factory):
    """Wipe seed rows before and after each test."""
    async def _wipe():
        async with async_db_factory() as s:
            await s.execute(delete(EventNewsLink).where(EventNewsLink.event_id == 601))
            await s.execute(delete(NewsClean).where(NewsClean.id.in_([1001, 1002, 1003, 1004])))
            await s.execute(delete(News).where(News.id.in_([9001, 9002, 9003, 9004])))
            await s.execute(delete(Event).where(Event.id == 601))
            await s.commit()
    await _wipe()
    yield
    await _wipe()


@pytest.mark.asyncio
async def test_pool_builder_respects_window_cutoff(async_db_factory, _clean_up):
    async with async_db_factory() as s:
        s.add(Event(id=601, event_title="e"))
        await s.flush()
        # 3 articles: 1h, 24h, 100h old. Window=72h should include first two.
        await _seed_article(s, clean_id=1001, news_id=9001, event_id=601,
                            age_hours=1, embedding=[0.1] * 1536)
        await _seed_article(s, clean_id=1002, news_id=9002, event_id=601,
                            age_hours=24, embedding=[0.1] * 1536)
        await _seed_article(s, clean_id=1003, news_id=9003, event_id=601,
                            age_hours=100, embedding=[0.1] * 1536)
        await s.commit()

    async with async_db_factory() as s:
        pool = await fetch_candidate_articles(s, event_id=601, t0=T0, window_hours=72)
    ids = {p["news_clean_id"] for p in pool}
    assert ids == {1001, 1002}


@pytest.mark.asyncio
async def test_pool_builder_only_articles_linked_to_event(async_db_factory, _clean_up):
    async with async_db_factory() as s:
        s.add(Event(id=601, event_title="e"))
        await s.flush()
        # Linked: 1001. Unlinked: 1002 (no EventNewsLink row for event 601).
        await _seed_article(s, clean_id=1001, news_id=9001, event_id=601,
                            age_hours=1, embedding=[0.1] * 1536)
        # Unlinked article: same insert but without the link
        s.add(News(id=9002, url="https://x/2", title="t", text="b",
                   source_name="src", source_tier=1, source_weight=0.5,
                   publish_date=T0 - timedelta(hours=1)))
        s.add(NewsClean(id=1002, news_id=9002, clean_text="clean", embedding=[0.1] * 1536))
        await s.commit()

    async with async_db_factory() as s:
        pool = await fetch_candidate_articles(s, event_id=601, t0=T0, window_hours=72)
    assert {p["news_clean_id"] for p in pool} == {1001}


@pytest.mark.asyncio
async def test_pool_builder_excludes_null_embeddings(async_db_factory, _clean_up):
    async with async_db_factory() as s:
        s.add(Event(id=601, event_title="e"))
        await s.flush()
        await _seed_article(s, clean_id=1001, news_id=9001, event_id=601,
                            age_hours=1, embedding=[0.1] * 1536)
        await _seed_article(s, clean_id=1002, news_id=9002, event_id=601,
                            age_hours=1, embedding=None)
        await s.commit()

    async with async_db_factory() as s:
        pool = await fetch_candidate_articles(s, event_id=601, t0=T0, window_hours=72)
    assert {p["news_clean_id"] for p in pool} == {1001}


@pytest.mark.asyncio
async def test_pool_builder_returns_required_fields(async_db_factory, _clean_up):
    async with async_db_factory() as s:
        s.add(Event(id=601, event_title="e"))
        await s.flush()
        await _seed_article(s, clean_id=1001, news_id=9001, event_id=601,
                            age_hours=3, embedding=[0.5] * 1536)
        await s.commit()

    async with async_db_factory() as s:
        pool = await fetch_candidate_articles(s, event_id=601, t0=T0, window_hours=72)
    assert len(pool) == 1
    item = pool[0]
    for k in ("news_clean_id", "embedding", "publish_date", "clean_text",
             "source_name", "source_tier", "source_weight"):
        assert k in item, f"missing key {k!r}"
    assert item["publish_date"] is not None
    assert item["source_tier"] == 1
