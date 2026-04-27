"""Celery task: compute the opposite-variant top-k for an event and record it.

Idempotent via the UNIQUE (event_id, variant, rank) constraint — retries are
safe. Kill-switched via `settings.ranking_shadow_enabled`.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.db.database import get_session_factory
from app.db.models import Event, EventMarketRankingShadow
from app.retrieval.ranking_variant import active_ranking_variant
from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.tasks_ranking_shadow.record_shadow_ranking",
    bind=True,
    rate_limit="120/m",
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
    reject_on_worker_lost=True,
)
def record_shadow_ranking(self, *, event_id: int) -> dict:
    """Compute and store the opposite-variant top-k ranking for `event_id`."""
    settings = get_settings()
    if not settings.ranking_shadow_enabled:
        return {"status": "disabled", "event_id": event_id}
    try:
        return _run_async(_do(event_id))
    except Exception as exc:
        logger.exception("record_shadow_ranking failed event_id=%s", event_id)
        raise self.retry(exc=exc, throw=False) from exc


async def _do(event_id: int) -> dict:
    prod_variant = active_ranking_variant()
    opposite = "v2" if prod_variant == "v1" else "v1"

    factory = get_session_factory()
    async with factory() as session:
        ev = (
            await session.execute(select(Event).where(Event.id == event_id))
        ).scalar_one_or_none()
        if ev is None or ev.embedding is None:
            return {"status": "skipped_no_embedding", "event_id": event_id}

        text = ev.event_retrieval_text or ev.event_title

        if opposite == "v2":
            from app.retrieval.hybrid_search_v2 import hybrid_search_markets_v2
            results = await hybrid_search_markets_v2(
                session, list(ev.embedding), text,
                top_k=5,
                event_bucket=ev.bucket,
                event_entities=ev.key_entities,
                event_last_seen=ev.last_seen,
            )
        else:
            from app.retrieval.hybrid_search import hybrid_search_markets
            results = await hybrid_search_markets(
                session, list(ev.embedding), text,
                top_k=5,
                event_bucket=ev.bucket,
                event_entities=ev.key_entities,
            )

        rows_inserted = 0
        for r in results:
            stmt = pg_insert(EventMarketRankingShadow).values(
                event_id=event_id,
                market_id=r["market_id"],
                variant=opposite,
                rank=r.get("rank"),
                rrf_score=r.get("rrf_score") or 0.0,
                cosine_score=r.get("cosine_score"),
                entity_matches=r.get("entity_matches"),
                date_proximity=r.get("date_proximity"),
                bucket_match=r.get("bucket_match"),
            ).on_conflict_do_nothing(constraint="uq_ranking_shadow_event_variant_rank")
            res = await session.execute(stmt)
            rows_inserted += int(res.rowcount or 0)
        await session.commit()

    return {
        "status": "ok",
        "event_id": event_id,
        "shadow_variant": opposite,
        "rows_inserted": rows_inserted,
        "top_k_size": len(results),
    }
