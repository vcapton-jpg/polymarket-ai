"""Celery tasks — scoring pipeline (hybrid search → LLM → score → signal).

Key optimisation: LLM impact analyses run in PARALLEL via asyncio.gather,
cutting the dominant latency from 5×sequential to 1×parallel.
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _signal_dedupe_key(market_id: str, event_title: str, bucket: Optional[str]) -> str:
    norm = f"{bucket or ''}|{market_id}|{(event_title or '').strip().lower()[:500]}"
    return hashlib.sha256(norm.encode()).hexdigest()[:48]


# ══════════════════════════════════════════════════════════════════════════
# Phase 5 — Hybrid search → LLM impact → score → signal (all in one task)
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def run_hybrid_search(self, event_id: int):
    """Find candidates, run parallel LLM analysis, generate signals — one task."""
    try:
        return _run_async(_run_full_scoring_pipeline(event_id))
    except Exception as exc:
        logger.exception("run_hybrid_search failed for event_id=%s", event_id)
        raise self.retry(exc=exc)


async def _run_full_scoring_pipeline(event_id: int) -> dict:
    """Combined hybrid-search + parallel-LLM + score pipeline in one async call."""
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import (
        Event,
        EventMarketAnalysis,
        EventMarketCandidate,
        Market,
        Signal,
    )
    from app.llm.impact_analyzer import create_impact_analyzer
    from app.processing.embedding_service import get_embedding
    from app.processing.freshness import signal_event_still_fresh
    from app.retrieval.hybrid_search import hybrid_search_markets
    from app.signal.signal_builder import create_signal_builder

    settings = get_settings()
    max_llm = settings.llm_impact_max_candidates

    async with async_session_factory() as session:
        event = (
            await session.execute(select(Event).where(Event.id == event_id))
        ).scalar_one_or_none()

        if not event:
            return {"status": "event_not_found", "event_id": event_id}

        if not signal_event_still_fresh(
            event.last_seen,
            max_age_hours=settings.signal_event_max_age_hours,
        ):
            event.processing_status = "skipped_stale"
            await session.commit()
            return {"status": "event_too_stale", "event_id": event_id}

        skip_llm = event.processing_status in ("llm_done", "scoring_done")

        # ── Step 1: Event embedding ──────────────────────────────────
        raw_embedding = event.embedding
        if raw_embedding is None:
            text_for_embed = event.event_retrieval_text or event.event_title
            raw_embedding = await get_embedding(text_for_embed)
            if raw_embedding is not None:
                event.embedding = raw_embedding
                await session.flush()

        if raw_embedding is None:
            event.processing_status = "failed_no_embedding"
            await session.commit()
            return {"status": "no_embedding", "event_id": event_id}

        embedding = list(raw_embedding)
        event_text = event.event_retrieval_text or event.event_title

        # ── Step 2: Hybrid search ────────────────────────────────────
        candidates = await hybrid_search_markets(
            session, embedding, event_text,
            event_bucket=event.bucket,
            event_entities=event.key_entities,
        )

        if not candidates:
            event.processing_status = "no_candidates"
            await session.commit()
            return {"status": "no_candidates", "event_id": event_id}

        for c in candidates:
            existing = (
                await session.execute(
                    select(EventMarketCandidate).where(
                        EventMarketCandidate.event_id == event_id,
                        EventMarketCandidate.market_id == c["market_id"],
                    )
                )
            ).scalar_one_or_none()

            if existing:
                existing.bm25_score = c.get("bm25_score")
                existing.cosine_score = c.get("cosine_score")
                existing.rrf_score = c.get("rrf_score")
                existing.rank = c.get("rank")
            else:
                session.add(EventMarketCandidate(
                    event_id=event_id,
                    market_id=c["market_id"],
                    bm25_score=c.get("bm25_score"),
                    cosine_score=c.get("cosine_score"),
                    rrf_score=c.get("rrf_score"),
                    rank=c.get("rank"),
                ))

        event.processing_status = "candidates_found"
        await session.flush()

        # ── Step 3: Parallel LLM impact analysis ─────────────────────
        top_cands = candidates[:max_llm]
        analyzed = 0
        llm_results: list = []

        if not skip_llm:
            event_full_text = f"{event.event_title}. {event.event_summary or ''}"
            analyzer = create_impact_analyzer()

            async def _analyze_one(cand_dict: dict) -> Optional[dict]:
                mid = cand_dict["market_id"]
                market = (
                    await session.execute(
                        select(Market).where(Market.market_id == mid)
                    )
                ).scalar_one_or_none()
                if not market:
                    return None

                already = (
                    await session.execute(
                        select(EventMarketAnalysis)
                        .where(
                            EventMarketAnalysis.event_id == event_id,
                            EventMarketAnalysis.market_id == mid,
                        )
                        .order_by(EventMarketAnalysis.id.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if already:
                    return {"market_id": mid, "skipped": True}

                result = await analyzer.analyze(event_full_text, market.question)
                if not result:
                    return None

                session.add(EventMarketAnalysis(
                    event_id=event_id,
                    market_id=mid,
                    impact_direction=result.get("impact_direction") or result.get("direction"),
                    impact_strength=_safe_float(result.get("impact_strength") or result.get("impact_score")),
                    llm_confidence=_safe_float(result.get("llm_confidence") or result.get("confidence")),
                    ambiguity_score=_safe_float(result.get("ambiguity_score")),
                    specificity_score=_safe_float(result.get("specificity_score")),
                    catalysts=result.get("catalysts"),
                    risks=result.get("risks"),
                    reasoning=result.get("reasoning"),
                ))
                return {"market_id": mid, "analysis": result}

            llm_results = await asyncio.gather(
                *[_analyze_one(c) for c in top_cands],
                return_exceptions=True,
            )

            for r in llm_results:
                if isinstance(r, dict) and not r.get("skipped"):
                    analyzed += 1
                elif isinstance(r, Exception):
                    logger.warning("LLM analysis failed: %s", r)

            event.processing_status = "llm_done"
            await session.flush()

        # ── Step 4: Score candidates, keep only the best signal per event ─
        builder = create_signal_builder()
        signals_created = 0
        best_signal = None
        best_signal_mid = None
        best_score = -1

        scored_mids = set()
        for r in llm_results:
            if not isinstance(r, dict) or "market_id" not in r:
                continue
            scored_mids.add(r["market_id"])

        all_analyses = (
            await session.execute(
                select(EventMarketAnalysis)
                .where(EventMarketAnalysis.event_id == event_id)
            )
        ).scalars().all()
        for a in all_analyses:
            scored_mids.add(a.market_id)

        cosine_by_mid = {}
        for c in candidates:
            cosine_by_mid[c["market_id"]] = c.get("cosine_score")

        for mid in scored_mids:
            market = (
                await session.execute(
                    select(Market).where(Market.market_id == mid)
                )
            ).scalar_one_or_none()
            if not market:
                continue

            if not signal_event_still_fresh(
                event.last_seen,
                max_age_hours=settings.signal_event_max_age_hours,
            ):
                break

            existing_signal = (
                await session.execute(
                    select(Signal)
                    .where(
                        Signal.event_id == event_id,
                        Signal.market_id == mid,
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if existing_signal:
                continue

            market_cooloff = datetime.now(timezone.utc) - timedelta(hours=6)
            recent_market_signal = (
                await session.execute(
                    select(Signal.id)
                    .where(
                        Signal.market_id == mid,
                        Signal.created_at >= market_cooloff,
                    )
                    .order_by(Signal.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if recent_market_signal:
                logger.info("Market cooloff: market %s already has signal in last 6h", mid)
                continue

            analysis = (
                await session.execute(
                    select(EventMarketAnalysis)
                    .where(
                        EventMarketAnalysis.event_id == event_id,
                        EventMarketAnalysis.market_id == mid,
                    )
                    .order_by(EventMarketAnalysis.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            event_data = {
                "first_seen": event.first_seen,
                "last_seen": event.last_seen,
                "unique_sources_count": event.unique_sources_count,
                "source_weight": 0.8,
            }
            market_data = {
                "liquidity": float(market.liquidity) if market.liquidity else None,
                "spread": float(market.spread) if market.spread else None,
                "end_date": market.end_date,
                "last_trade_price": float(market.last_trade_price) if market.last_trade_price else None,
            }
            llm_data = None
            if analysis:
                llm_data = {
                    "impact_direction": analysis.impact_direction,
                    "impact_strength": float(analysis.impact_strength) if analysis.impact_strength else None,
                    "llm_confidence": float(analysis.llm_confidence) if analysis.llm_confidence else None,
                    "ambiguity_score": float(analysis.ambiguity_score) if analysis.ambiguity_score else None,
                    "specificity_score": float(analysis.specificity_score) if analysis.specificity_score else None,
                }

            mid_cosine = cosine_by_mid.get(mid)
            signal = builder.build_signal(
                event_id, mid, event_data, market_data, llm_data,
                cosine_score=mid_cosine,
            )
            if signal is None:
                continue

            signal.score_label = getattr(signal, "_score_label", None)
            signal.score_explanation = getattr(signal, "_score_explanation", None)
            signal.window_estimate = getattr(signal, "_window_estimate", None)
            signal.yes_probability_explanation = getattr(signal, "_yes_probability_explanation", None)
            is_below = getattr(signal, "_below_threshold", False)

            if is_below:
                dedupe_key = _signal_dedupe_key(mid, event.event_title, event.bucket)
                signal.dedupe_key = dedupe_key
                session.add(signal)
                await session.flush()
                logger.info(
                    "Sub-threshold signal logged: id=%d event=%d market=%s score=%.1f",
                    signal.id, event_id, mid, signal.signal_score,
                )
                continue

            if signal.signal_score > best_score:
                best_score = signal.signal_score
                best_signal = signal
                best_signal_mid = mid

        if best_signal is not None:
            dedupe_key = _signal_dedupe_key(best_signal_mid, event.event_title, event.bucket)
            best_signal.dedupe_key = dedupe_key
            session.add(best_signal)
            await session.flush()

            _schedule_price_captures(best_signal.id, best_signal_mid)
            _broadcast_signal(best_signal)
            signals_created = 1

            logger.info(
                "Signal created: id=%d event=%d market=%s score=%.1f dir=%s",
                best_signal.id, event_id, best_signal_mid,
                best_signal.signal_score, best_signal.direction,
            )

        event.processing_status = "scoring_done"
        await session.commit()

    logger.info(
        "Scoring pipeline: event=%d → %d candidates, %d LLM analyses, %d signals",
        event_id, len(candidates), analyzed, signals_created,
    )
    return {
        "status": "ok",
        "event_id": event_id,
        "candidates": len(candidates),
        "analyzed": analyzed,
        "signals_created": signals_created,
    }


# ══════════════════════════════════════════════════════════════════════════
# Legacy entry points (kept for backward-compatible beat schedule dispatch)
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_llm_impact(self, event_id: int):
    """Redirects to full scoring pipeline."""
    try:
        return _run_async(_run_full_scoring_pipeline(event_id))
    except Exception as exc:
        logger.exception("run_llm_impact failed for event_id=%s", event_id)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=1)
def compute_score_and_signal(self, event_id: int, market_id: str):
    """Legacy — full pipeline already handles scoring inline."""
    return {"status": "handled_by_full_pipeline", "event_id": event_id, "market_id": market_id}


# ══════════════════════════════════════════════════════════════════════════
# Retry stuck events
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=1)
def retry_stuck_events(self):
    try:
        return _run_async(_retry_stuck_events_async())
    except Exception as exc:
        logger.exception("retry_stuck_events failed")
        raise self.retry(exc=exc)


async def _retry_stuck_events_async() -> dict:
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import Event
    from app.processing.freshness import signal_event_still_fresh

    settings = get_settings()

    retryable = ["candidates_found", "new", "no_candidates", "llm_done"]

    async with async_session_factory() as session:
        stuck = (
            await session.execute(
                select(Event)
                .where(Event.processing_status.in_(retryable))
                .order_by(Event.last_seen.desc())
                .limit(30)
            )
        ).scalars().all()

        if not stuck:
            return {"status": "nothing_stuck"}

        dispatched = 0
        skipped_stale = 0
        for event in stuck:
            if not signal_event_still_fresh(
                event.last_seen,
                max_age_hours=settings.signal_event_max_age_hours,
            ):
                event.processing_status = "skipped_stale"
                skipped_stale += 1
                continue
            run_hybrid_search.apply_async(args=[event.id], queue="scoring")
            dispatched += 1

        await session.commit()

    logger.info("retry_stuck_events: dispatched=%d skipped_stale=%d", dispatched, skipped_stale)
    return {"status": "ok", "dispatched": dispatched, "skipped_stale": skipped_stale}


# ══════════════════════════════════════════════════════════════════════════
# Re-score events that completed scoring but produced 0 signals
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=1)
def rescore_zero_signal_events(self):
    try:
        return _run_async(_rescore_zero_signal_events_async())
    except Exception as exc:
        logger.exception("rescore_zero_signal_events failed")
        raise self.retry(exc=exc)


async def _rescore_zero_signal_events_async() -> dict:
    from sqlalchemy import func, select

    from app.core.config import get_settings
    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import Event, Signal
    from app.processing.freshness import signal_event_still_fresh

    settings = get_settings()

    async with async_session_factory() as session:
        signal_event_ids = select(Signal.event_id).distinct().scalar_subquery()

        zero_signal_events = (
            await session.execute(
                select(Event)
                .where(
                    Event.processing_status == "scoring_done",
                    Event.id.not_in(signal_event_ids),
                )
                .order_by(Event.last_seen.desc())
                .limit(20)
            )
        ).scalars().all()

        if not zero_signal_events:
            return {"status": "nothing_to_rescore"}

        dispatched = 0
        skipped_stale = 0
        for event in zero_signal_events:
            if not signal_event_still_fresh(
                event.last_seen,
                max_age_hours=settings.signal_event_max_age_hours,
            ):
                skipped_stale += 1
                continue
            event.processing_status = "candidates_found"
            run_hybrid_search.apply_async(args=[event.id], queue="scoring")
            dispatched += 1

        await session.commit()

    logger.info("rescore_zero_signal: dispatched=%d skipped_stale=%d", dispatched, skipped_stale)
    return {"status": "ok", "dispatched": dispatched, "skipped_stale": skipped_stale}


# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════

def _schedule_price_captures(signal_id: int, market_id: str):
    from app.workers.tasks_outcomes import capture_price

    delays = [
        ("price_t5min", 5 * 60),
        ("price_t15min", 15 * 60),
        ("price_t1h", 60 * 60),
        ("price_t24h", 24 * 60 * 60),
    ]
    for field, countdown in delays:
        capture_price.apply_async(
            args=[signal_id, market_id, field],
            countdown=countdown,
            queue="default",
        )


def _broadcast_signal(signal):
    """Push signal to Redis pub/sub (for WebSocket clients) + Telegram."""
    import json

    payload = {
        "id": signal.id,
        "event_id": signal.event_id,
        "market_id": signal.market_id,
        "signal_score": float(signal.signal_score),
        "signal_strength": float(signal.signal_strength) if signal.signal_strength is not None else None,
        "trade_quality": float(signal.trade_quality) if signal.trade_quality is not None else None,
        "direction": signal.direction,
        "confidence_label": signal.confidence_label,
        "urgency_label": signal.urgency_label,
        "tradability_label": signal.tradability_label,
        "market_price_at_signal": float(signal.market_price_at_signal) if signal.market_price_at_signal else None,
        "created_at": signal.created_at.isoformat() if signal.created_at else None,
    }

    try:
        import redis as _redis
        from app.core.config import get_settings
        _settings = get_settings()
        r = _redis.from_url(_settings.redis_url)
        r.publish("signal:new", json.dumps(payload))
        r.close()
        logger.info("Broadcast signal id=%d to Redis pub/sub", signal.id)
    except Exception:
        logger.warning("Redis broadcast failed for signal id=%d", signal.id, exc_info=True)

    _send_telegram_alert(signal)
    _send_push_notification(signal)


def _send_telegram_alert(signal):
    """Send a Telegram message for high-conviction signals."""
    from app.core.config import get_settings

    settings = get_settings()
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id

    if not token or not chat_id:
        return

    score = float(signal.signal_score)
    if score < settings.signal_score_threshold:
        return

    direction = signal.direction or "NEUTRAL"
    price_str = f"{float(signal.market_price_at_signal) * 100:.1f}%" if signal.market_price_at_signal else "--"
    conf = (signal.confidence_label or "").upper()
    urgency = (signal.urgency_label or "").upper()

    if score >= 90:
        tier = "EXCEPTIONAL"
    elif score >= 75:
        tier = "HIGH CONVICTION"
    elif score >= 60:
        tier = "ACTIONABLE"
    else:
        tier = "MONITORING"

    text = (
        f"{'🟢' if 'YES' in direction else '🔴'} *Signal #{signal.id}* — {tier}\n\n"
        f"*Score:* {score:.0f}/100\n"
        f"*Direction:* {direction}\n"
        f"*Market price:* {price_str} YES\n"
        f"*Confidence:* {conf}\n"
        f"*Urgency:* {urgency}\n\n"
        f"[Open in Signal](https://signal.app/opportunity/{signal.id})"
    )

    try:
        import httpx
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info("Telegram alert sent for signal id=%d", signal.id)
        else:
            logger.warning("Telegram API returned %d: %s", resp.status_code, resp.text[:200])
    except Exception:
        logger.warning("Telegram alert failed for signal id=%d", signal.id, exc_info=True)


def _send_push_notification(signal):
    """Send PWA push notification for high-conviction signals."""
    score = float(signal.signal_score)
    if score < 60:
        return
    try:
        from app.api.push import send_push_to_all
        direction = signal.direction or "NEUTRAL"
        send_push_to_all(
            title=f"Signal #{signal.id} — {score:.0f}/100",
            body=f"{direction} | Market price {float(signal.market_price_at_signal) * 100:.0f}% YES" if signal.market_price_at_signal else f"{direction}",
            url=f"/opportunity/{signal.id}",
            tag=f"signal-{signal.id}",
        )
    except Exception:
        logger.debug("Push notification failed for signal %d", signal.id, exc_info=True)


def _safe_float(val, scale: int = 1) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val) / scale
    except (ValueError, TypeError):
        return None


def _is_quota_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return (
        "insufficient_quota" in msg
        or "quota" in msg
        or "429" in msg
        or "rate limit" in msg
    )


async def _score_event_market_async(event, market, articles, *, analyzer=None):
    from app.llm.reasoning_analyzer import create_reasoning_analyzer
    from app.signal.signal_builder import build_signal
    from app.db.database import get_session_factory
    from app.db.models import SignalPendingReasoning

    analyzer = analyzer or create_reasoning_analyzer()

    try:
        return await build_signal(
            event=event, market=market, articles=articles,
            analyzer=analyzer, persist=True,
        )
    except Exception as e:
        if _is_quota_error(e):
            logger.warning(
                "llm.quota_exceeded event_id=%s market_id=%s — staging for backfill",
                event.get("id"), market.get("id"),
            )
            session_factory = get_session_factory()
            async with session_factory() as s:
                s.add(SignalPendingReasoning(
                    event_id=event["id"],
                    market_id=market["id"],
                    inputs={
                        "event": event, "market": market, "articles": articles,
                    },
                    last_error=str(e)[:500],
                ))
                await s.commit()
            return None
        raise
