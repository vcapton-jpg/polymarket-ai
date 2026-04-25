"""Single source of truth for Event.{articles,unique_sources}_count.

Both columns were originally set at event creation and never updated. The
fix is to recompute from the live `event_news_links` join after every
mutation that adds or removes a link.

Kept in its own module (not on the model class) so that:
  - Both the fast path and the batch path call the same code
  - The backfill script can repair stale rows without going through the
    creation flow
  - It can be unit-tested in isolation against a real session
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.db.models import Event, EventNewsLink, News, NewsClean

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def recompute_event_counts(session: "AsyncSession", *, event_id: int) -> None:
    """Refresh Event.articles_count + Event.unique_sources_count for one event.

    Caller is responsible for the surrounding transaction — this helper
    issues the SELECT + UPDATE on the open session and does NOT commit.

    Counts are clamped to >= 1: an event row implies at least one article
    by construction; a zero count would silently violate that and surface
    as `0 sources` in the UI mid-creation.
    """
    row = (
        await session.execute(
            select(
                func.count(EventNewsLink.id).label("articles"),
                func.count(func.distinct(News.source_name)).label("sources"),
            )
            .select_from(EventNewsLink)
            .join(NewsClean, NewsClean.id == EventNewsLink.clean_id)
            .join(News, News.id == NewsClean.news_id)
            .where(EventNewsLink.event_id == event_id)
        )
    ).one()

    articles = max(1, int(row.articles or 0))
    sources = max(1, int(row.sources or 0))

    ev = await session.get(Event, event_id)
    if ev is None:
        return
    ev.articles_count = articles
    ev.unique_sources_count = sources
