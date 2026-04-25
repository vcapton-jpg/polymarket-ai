"""recompute_event_counts(event_id) keeps Event.{articles,unique_sources}_count
in sync with the live event_news_links state.

Pre-fix bug (audit 2026-04-25): both columns are written once at event
creation in event_builder/tasks_pipeline and never updated. Adding a new
EventNewsLink for an existing event leaves the stored counts stale; the
API and signal_mapper read the stale value while the scorer correctly
recomputes from the JOIN.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete

from app.db.models import Event, EventNewsLink, News, NewsClean


@pytest.mark.asyncio
async def test_recompute_updates_counts_after_new_link(async_db_factory):
    from app.event_engine.event_counts import recompute_event_counts

    EVENT_ID = 993100
    URL_BASE = "https://example.com/recompute-"

    async with async_db_factory() as s:
        s.add(Event(
            id=EVENT_ID, event_title="e",
            articles_count=1, unique_sources_count=1,
        ))
        n1 = News(
            url=URL_BASE + "1", title="t1", source_name="reuters",
            source_tier=1, source_weight=0.95,
        )
        n2 = News(
            url=URL_BASE + "2", title="t2", source_name="bloomberg",
            source_tier=1, source_weight=0.95,
        )
        s.add_all([n1, n2])
        await s.flush()
        c1 = NewsClean(news_id=n1.id, clean_text="t1 body")
        c2 = NewsClean(news_id=n2.id, clean_text="t2 body")
        s.add_all([c1, c2])
        await s.flush()
        s.add(EventNewsLink(event_id=EVENT_ID, clean_id=c1.id))
        s.add(EventNewsLink(event_id=EVENT_ID, clean_id=c2.id))
        await s.commit()

    try:
        async with async_db_factory() as s:
            await recompute_event_counts(s, event_id=EVENT_ID)
            await s.commit()

            ev = (await s.get(Event, EVENT_ID))
            assert ev.articles_count == 2, "articles_count not refreshed"
            assert ev.unique_sources_count == 2, (
                "unique_sources_count still stale — recompute_event_counts "
                "did not update Event row from event_news_links JOIN"
            )
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(EventNewsLink).where(EventNewsLink.event_id == EVENT_ID))
            await s.execute(delete(NewsClean).where(NewsClean.news.has(News.url.startswith(URL_BASE))))
            await s.execute(delete(News).where(News.url.startswith(URL_BASE)))
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.commit()


def test_recompute_is_called_from_both_event_creation_paths():
    """Static check — chantier-2 bug 3 regression net.

    `tasks_pipeline.py` has two distinct sites that insert EventNewsLink
    rows (the fast `_try_instant_event_async` path and the batch backfill
    path). Both MUST call `recompute_event_counts` after the inserts so
    `Event.unique_sources_count` cannot drift from the JOIN truth.

    A grep-based pin is enough here — the helper itself is tested
    behaviorally above; we just need to make sure nothing accidentally
    drops the call site.
    """
    from app.workers import tasks_pipeline as tp

    src = open(tp.__file__, encoding="utf-8").read()
    # Two call sites: fast path + batch path.
    assert src.count("recompute_event_counts(session, event_id=event.id)") >= 2, (
        "recompute_event_counts must be called from BOTH event-creation "
        "sites in tasks_pipeline.py — see chantier-2 plan, Task 4."
    )


@pytest.mark.asyncio
async def test_recompute_handles_event_with_no_links(async_db_factory):
    """Edge case: event exists but has zero links yet (creation-in-progress).
    Helper must not crash and must clamp counts to >= 1 (the column has a
    NOT NULL default of 1; zero would violate the soft contract that an
    event always represents at least one article)."""
    from app.event_engine.event_counts import recompute_event_counts

    EVENT_ID = 993101
    async with async_db_factory() as s:
        s.add(Event(
            id=EVENT_ID, event_title="orphan",
            articles_count=1, unique_sources_count=1,
        ))
        await s.commit()
    try:
        async with async_db_factory() as s:
            await recompute_event_counts(s, event_id=EVENT_ID)
            await s.commit()
            ev = await s.get(Event, EVENT_ID)
            assert ev.articles_count >= 1
            assert ev.unique_sources_count >= 1
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.commit()
