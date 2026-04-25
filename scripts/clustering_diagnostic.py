"""Print the current distribution of event-cluster diversity.

Read-only — safe to run against prod. Used as a before/after measurement
for the clustering-hardening chantier.

Usage:
    docker compose exec app python -m scripts.clustering_diagnostic
"""

from __future__ import annotations

import asyncio
from sqlalchemy import func, select

from app.db.database import get_session_factory
from app.db.models import Event, EventNewsLink, News, NewsClean


async def main() -> None:
    session_factory = get_session_factory()
    async with session_factory() as s:
        # Stored column distribution (what the API/UI sees today)
        rows = (await s.execute(
            select(Event.unique_sources_count, func.count(Event.id))
            .group_by(Event.unique_sources_count)
            .order_by(Event.unique_sources_count)
        )).all()
        print("Event.unique_sources_count (STORED):")
        total = sum(c for _, c in rows) or 1
        for v, c in rows:
            print(f"  {v:>3} | {c:>6} ({100*c/total:5.1f}%)")

        # Live recomputed unique-source distribution — apples-to-apples
        # comparison with the STORED unique_sources_count column above.
        # Joins through NewsClean → News so we count distinct source_name,
        # not distinct clean_id, and reproduce the exact logic in
        # recompute_event_counts.
        live_sources_subq = (
            select(
                EventNewsLink.event_id,
                func.count(func.distinct(News.source_name)).label("sources"),
            )
            .select_from(EventNewsLink)
            .join(NewsClean, NewsClean.id == EventNewsLink.clean_id)
            .join(News, News.id == NewsClean.news_id)
            .group_by(EventNewsLink.event_id)
            .subquery()
        )
        live_src_rows = (await s.execute(
            select(live_sources_subq.c.sources, func.count())
            .group_by(live_sources_subq.c.sources)
            .order_by(live_sources_subq.c.sources)
        )).all()
        print("\nEvent unique-source count (LIVE from JOIN):")
        total = sum(c for _, c in live_src_rows) or 1
        for v, c in live_src_rows:
            print(f"  {v:>3} | {c:>6} ({100*c/total:5.1f}%)")

        # Bonus: link-count distribution (articles per event), useful for
        # "how often does the cluster have more than one article at all".
        live_links_subq = (
            select(
                EventNewsLink.event_id,
                func.count(func.distinct(EventNewsLink.clean_id)).label("links"),
            )
            .group_by(EventNewsLink.event_id)
            .subquery()
        )
        live_link_rows = (await s.execute(
            select(live_links_subq.c.links, func.count())
            .group_by(live_links_subq.c.links)
            .order_by(live_links_subq.c.links)
        )).all()
        print("\nEvent link count (LIVE — articles per event):")
        total = sum(c for _, c in live_link_rows) or 1
        for v, c in live_link_rows:
            print(f"  {v:>3} | {c:>6} ({100*c/total:5.1f}%)")


if __name__ == "__main__":
    asyncio.run(main())
