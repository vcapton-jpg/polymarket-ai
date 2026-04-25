"""One-shot backfill: refresh Event.{articles,unique_sources}_count from
the live event_news_links state for every event in the database.

Usage:
    docker compose exec app python -m scripts.backfill_event_counts --dry-run
    docker compose exec app python -m scripts.backfill_event_counts

Idempotent — safe to re-run. Batched per 500 events to keep the
transaction short.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from sqlalchemy import select

from app.db.database import get_session_factory
from app.db.models import Event
from app.event_engine.event_counts import recompute_event_counts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BATCH_SIZE = 500


async def main(dry_run: bool) -> None:
    session_factory = get_session_factory()
    async with session_factory() as s:
        ids = (await s.execute(select(Event.id).order_by(Event.id))).scalars().all()
    logger.info("backfill_event_counts: %d events to process", len(ids))

    changed = 0
    for offset in range(0, len(ids), BATCH_SIZE):
        batch = ids[offset:offset + BATCH_SIZE]
        async with session_factory() as s:
            for event_id in batch:
                ev = await s.get(Event, event_id)
                if ev is None:
                    continue
                before = (ev.articles_count, ev.unique_sources_count)
                await recompute_event_counts(s, event_id=event_id)
                after = (ev.articles_count, ev.unique_sources_count)
                if before != after:
                    changed += 1
                    logger.info(
                        "event %s: (a=%d s=%d) -> (a=%d s=%d)",
                        event_id, before[0], before[1], after[0], after[1],
                    )
            if dry_run:
                await s.rollback()
            else:
                await s.commit()
        logger.info("processed %d / %d", offset + len(batch), len(ids))
    logger.info("backfill_event_counts: changed=%d dry_run=%s", changed, dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
