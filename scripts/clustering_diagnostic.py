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
from app.db.models import Event, EventNewsLink


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

        # Live recomputed distribution from EventNewsLink (the truth)
        live_subq = (
            select(
                EventNewsLink.event_id,
                func.count(func.distinct(EventNewsLink.clean_id)).label("links"),
            )
            .group_by(EventNewsLink.event_id)
            .subquery()
        )
        live_rows = (await s.execute(
            select(live_subq.c.links, func.count())
            .group_by(live_subq.c.links)
            .order_by(live_subq.c.links)
        )).all()
        print("\nEvent link count (LIVE from event_news_links):")
        total = sum(c for _, c in live_rows) or 1
        for v, c in live_rows:
            print(f"  {v:>3} | {c:>6} ({100*c/total:5.1f}%)")


if __name__ == "__main__":
    asyncio.run(main())
