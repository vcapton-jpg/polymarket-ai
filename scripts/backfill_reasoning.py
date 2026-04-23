"""One-off: backfill `reasoning` + `source_tier_mix` for pre-Axis-A signals.

Usage:
    docker compose exec app python -m scripts.backfill_reasoning --days 7 --dry-run
    docker compose exec app python -m scripts.backfill_reasoning --days 7
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.database import get_session_factory
from app.db.models import EventNewsLink, News, NewsClean, Signal, SourceRegistry
from app.llm.reasoning_analyzer import create_reasoning_analyzer
from app.signal.signal_builder import build_signal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main(days: int, dry_run: bool) -> None:
    analyzer = create_reasoning_analyzer()
    session_factory = get_session_factory()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with session_factory() as s:
        rows = (
            await s.execute(
                select(Signal)
                .where(
                    Signal.reasoning.is_(None),
                    Signal.created_at >= cutoff,
                )
                .order_by(Signal.created_at.desc())
            )
        ).scalars().all()

    logger.info("backfill: candidates=%d dry_run=%s", len(rows), dry_run)
    filled = 0
    rejected = 0
    for sig in rows:
        async with session_factory() as s:
            arts_rows = (
                await s.execute(
                    select(News, NewsClean, SourceRegistry)
                    .join(NewsClean, NewsClean.news_id == News.id)
                    .join(EventNewsLink, EventNewsLink.clean_id == NewsClean.id)
                    .join(
                        SourceRegistry,
                        SourceRegistry.id == News.source_id,
                        isouter=True,
                    )
                    .where(EventNewsLink.event_id == sig.event_id)
                    .limit(5)
                )
            ).all()

        articles = [
            {
                "news_clean_id": nc.id,
                "title": n.title or "",
                "source_name": (sr.source_name if sr else n.source_name) or "unknown",
                "source_tier": (sr.tier if sr else n.source_tier) or 3,
                "clean_text": nc.clean_text or "",
                "publish_date": n.publish_date.isoformat() if n.publish_date else None,
            }
            for (n, nc, sr) in arts_rows
        ]
        if not articles:
            continue

        if dry_run:
            logger.info("[dry-run] would backfill signal id=%s", sig.id)
            continue

        try:
            result = await build_signal(
                event={"id": sig.event_id, "title": "(legacy)", "summary": ""},
                market={"id": sig.market_id, "question": "(legacy)", "price": 0.5},
                articles=articles,
                analyzer=analyzer,
                persist=False,
            )
        except Exception as e:
            logger.warning("backfill: build_signal error id=%s: %s", sig.id, e)
            rejected += 1
            continue

        if result is None:
            logger.info("backfill: rejected id=%s", sig.id)
            rejected += 1
            continue

        async with session_factory() as s:
            merged = await s.merge(sig)
            merged.reasoning = result["reasoning"]
            merged.llm_model_version = result["llm_model_version"]
            merged.source_tier_mix = result["source_tier_mix"]
            await s.commit()
        filled += 1
        logger.info("backfill: filled id=%s", sig.id)

    logger.info("backfill: done filled=%d rejected=%d", filled, rejected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.days, args.dry_run))
