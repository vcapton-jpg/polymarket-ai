"""Celery task: backfill `embedding_v2` for rows where it is NULL.

Invoked manually per surface after a new v2 composer lands. Never scheduled
on beat — this is an operator-triggered task, not a background job.

Idempotent: never touches a row whose embedding_v2 is already populated.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.db.database import get_session_factory
from app.db.models import Event, Market, News, NewsClean
from app.processing.embedding_service import get_embedding
from app.processing.text_composers import (
    compose_event_v2,
    compose_market_v2,
    compose_news_v2,
)
from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.tasks_embeddings_backfill.recompute_embedding_v2",
    bind=True,
    rate_limit="60/m",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
    reject_on_worker_lost=True,
)
def recompute_embedding_v2(self, *, surface: str, batch_size: int = 100) -> dict:
    """Process one batch of rows lacking embedding_v2 for `surface`.

    Returns {'processed': int, 'remaining': int, 'est_cost_usd': float}.
    Caller loops manually (or invokes from a shell) until `remaining == 0`.
    """
    try:
        return _run_async(_run_backfill(surface, batch_size))
    except Exception as exc:
        logger.exception("recompute_embedding_v2 failed surface=%s", surface)
        raise self.retry(exc=exc, throw=False) from exc


async def _run_backfill(surface: str, batch_size: int) -> dict:
    if surface not in ("news", "market", "event"):
        raise ValueError(f"Unknown surface {surface!r}")

    factory = get_session_factory()
    processed = 0
    async with factory() as session:
        if surface == "news":
            stmt = (
                select(NewsClean)
                .options(joinedload(NewsClean.news))
                .where(NewsClean.embedding_v2.is_(None))
                .limit(batch_size)
            )
            rows = (await session.execute(stmt)).scalars().all()
            for nc in rows:
                title = (nc.news.title if nc.news is not None else "") or ""
                composed = compose_news_v2(title, nc.clean_text or "")
                emb = await get_embedding(composed.text)
                if emb is None:
                    continue
                nc.embedding_v2 = emb
                nc.embedding_v2_composition = composed.composition_version
                nc.embedding_v2_computed_at = datetime.now(timezone.utc)
                processed += 1
            remaining = (await session.execute(
                select(func.count()).select_from(NewsClean).where(NewsClean.embedding_v2.is_(None))
            )).scalar() or 0

        elif surface == "market":
            stmt = (
                select(Market)
                .where(Market.embedding_v2.is_(None))
                .limit(batch_size)
            )
            rows = (await session.execute(stmt)).scalars().all()
            for m in rows:
                composed = compose_market_v2({
                    "question": m.question,
                    "description": m.description,
                    "tags": m.tags,
                    "category": m.category,
                })
                emb = await get_embedding(composed.text)
                if emb is None:
                    continue
                m.embedding_v2 = emb
                m.embedding_v2_composition = composed.composition_version
                m.embedding_v2_computed_at = datetime.now(timezone.utc)
                processed += 1
            remaining = (await session.execute(
                select(func.count()).select_from(Market).where(Market.embedding_v2.is_(None))
            )).scalar() or 0

        else:  # event
            stmt = (
                select(Event)
                .where(Event.embedding_v2.is_(None))
                .limit(batch_size)
            )
            rows = (await session.execute(stmt)).scalars().all()
            for ev in rows:
                composed = compose_event_v2(
                    ev.event_title,
                    ev.event_summary or "",
                    list(ev.key_entities or []),
                    bucket=ev.bucket,
                )
                emb = await get_embedding(composed.text)
                if emb is None:
                    continue
                ev.embedding_v2 = emb
                ev.embedding_v2_composition = composed.composition_version
                ev.embedding_v2_computed_at = datetime.now(timezone.utc)
                processed += 1
            remaining = (await session.execute(
                select(func.count()).select_from(Event).where(Event.embedding_v2.is_(None))
            )).scalar() or 0

        await session.commit()

    est_cost = processed * 0.00001  # rough — $0.02/M tokens × ~500 tokens/row
    logger.info(
        "backfill surface=%s processed=%d remaining=%d est_cost_usd=%.4f",
        surface, processed, remaining, est_cost,
    )
    return {"processed": processed, "remaining": int(remaining), "est_cost_usd": est_cost}
