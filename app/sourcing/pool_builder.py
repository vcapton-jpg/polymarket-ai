"""Candidate-article pool for per-signal re-ranking.

Returns all articles linked to an event, published within `[t0 - window, t0]`,
with a non-NULL embedding. The ranker is the consumer; it re-sorts by score.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EventNewsLink, News, NewsClean


async def fetch_candidate_articles(
    session: AsyncSession,
    *,
    event_id: int,
    t0: datetime,
    window_hours: int = 72,
) -> list[dict[str, Any]]:
    """Fetch the candidate pool for `(event_id, t0)`.

    Filters:
      - linked to `event_id` via `event_news_links`
      - `news.publish_date` within `[t0 - window_hours, t0]`
      - `news_clean.embedding IS NOT NULL`

    Returns a list of dicts with the fields the ranker expects.
    """
    cutoff_lo = t0 - timedelta(hours=window_hours)

    stmt = (
        select(
            NewsClean.id.label("news_clean_id"),
            NewsClean.embedding,
            News.publish_date,
            NewsClean.clean_text,
            News.source_name,
            News.source_tier,
            News.source_weight,
        )
        .join(News, News.id == NewsClean.news_id)
        .join(EventNewsLink, EventNewsLink.clean_id == NewsClean.id)
        .where(
            EventNewsLink.event_id == event_id,
            News.publish_date.is_not(None),
            News.publish_date >= cutoff_lo,
            News.publish_date <= t0,
            NewsClean.embedding.is_not(None),
        )
        .order_by(News.publish_date.desc())
    )

    result = await session.execute(stmt)
    return [dict(row._mapping) for row in result.all()]
