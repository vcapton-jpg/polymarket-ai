"""Celery task: shadow-rerun the sourcing step for a newly-persisted signal."""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.db.database import get_session_factory
from app.db.models import (
    Market,
    Signal,
    SignalArticle,
    SignalPrediction,
)
from app.llm.reasoning_analyzer import get_reasoning_analyzer
from app.sourcing.article_ranker import ArticleRanker
from app.sourcing.pool_builder import fetch_candidate_articles
from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


SHADOW_VARIANT = "signal_v2_reranked"


@celery_app.task(
    name="app.workers.tasks_sourcing.sourcing_shadow_rerun",
    bind=True,
    rate_limit="30/m",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def sourcing_shadow_rerun(self, signal_id: int) -> None:
    try:
        return _run_async(_run_shadow(signal_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("sourcing_shadow_rerun failed signal_id=%s: %s", signal_id, exc)
        raise self.retry(exc=exc, throw=False) from exc


def _dir_llm_to_db(d: str | None) -> str | None:
    """Map the analyzer's 'YES'/'NO'/'UNCLEAR' to the DB enum. Returns None on UNCLEAR."""
    if not d:
        return None
    u = d.upper()
    if u == "YES":
        return "BUY_YES"
    if u == "NO":
        return "BUY_NO"
    return None


async def _run_shadow(signal_id: int) -> None:
    settings = get_settings()
    if not settings.sourcing_shadow_enabled:
        logger.debug("sourcing_shadow_rerun: killed by flag signal_id=%s", signal_id)
        return

    factory = get_session_factory()
    async with factory() as s:
        # Idempotency gate
        existing = (await s.execute(
            select(SignalPrediction).where(
                SignalPrediction.signal_id == signal_id,
                SignalPrediction.variant == SHADOW_VARIANT,
            )
        )).scalar_one_or_none()
        if existing is not None:
            return

        sig = await s.get(Signal, signal_id)
        if sig is None:
            logger.info("sourcing_shadow_rerun: signal vanished id=%s", signal_id)
            return

        market = await s.get(Market, sig.market_id)
        if market is None:
            logger.info("sourcing_shadow_rerun: market missing id=%s", sig.market_id)
            return

        pool = await fetch_candidate_articles(
            s,
            event_id=sig.event_id,
            t0=sig.created_at,
            window_hours=settings.sourcing_pool_window_hours,
        )
        if not pool:
            logger.debug("sourcing_shadow_rerun: empty pool event_id=%s", sig.event_id)
            return

        ranker = ArticleRanker.from_settings(settings)
        ranked = ranker.rank(
            pool,
            market.embedding,
            sig.created_at,
            top_k=settings.sourcing_top_k,
        )
        if not ranked:
            return

        # Build the dict shape reasoning_analyzer expects.
        by_id = {p["news_clean_id"]: p for p in pool}
        article_dicts = []
        for r in ranked:
            p = by_id[r.news_clean_id]
            article_dicts.append({
                "news_clean_id": r.news_clean_id,
                "title": p.get("clean_text", "")[:120],  # title field absent on clean; truncate body as stand-in
                "source_name": p["source_name"],
                "source_tier": p["source_tier"],
                "publish_date": p["publish_date"].isoformat() if p.get("publish_date") else None,
                "clean_text": p["clean_text"],
            })

        analyzer = get_reasoning_analyzer()
        # Event/market dicts the analyzer expects:
        event = {"title": "", "summary": ""}
        try:
            from app.db.models import Event
            ev = await s.get(Event, sig.event_id) if sig.event_id else None
            if ev is not None:
                event = {"title": ev.event_title, "summary": ev.event_summary or ""}
        except Exception:
            pass

        llm = await analyzer.analyze(
            event_title=event["title"],
            event_summary=event["summary"],
            articles=article_dicts,
            market_question=market.question,
            market_price=float(sig.market_price_at_signal or 0.0),
        )
        if llm is None:
            logger.info("sourcing_shadow_rerun: analyzer returned None signal_id=%s", signal_id)
            return

        # Excerpts per news_clean_id so we can store them on SignalArticle rows
        excerpts_by_id: dict[int, str] = {}
        for exc in (llm.get("article_excerpts") or []):
            ncid = exc.get("news_clean_id")
            if ncid is not None and exc.get("excerpt"):
                excerpts_by_id[int(ncid)] = exc["excerpt"]

        direction = _dir_llm_to_db(llm.get("direction_recommendation"))
        prob = llm.get("impact_score")
        try:
            prob = float(prob) if prob is not None else None
        except (TypeError, ValueError):
            prob = None

        s.add(SignalPrediction(
            signal_id=signal_id,
            variant=SHADOW_VARIANT,
            predicted_direction=direction,
            predicted_probability=prob,
        ))
        for r in ranked:
            s.add(SignalArticle(
                signal_id=signal_id,
                variant=SHADOW_VARIANT,
                news_clean_id=r.news_clean_id,
                rank=r.rank,
                score=float(r.score),
                cosine_score=float(r.cosine),
                recency_weight=float(r.recency_weight),
                excerpt=excerpts_by_id.get(r.news_clean_id),
            ))
        await s.commit()
