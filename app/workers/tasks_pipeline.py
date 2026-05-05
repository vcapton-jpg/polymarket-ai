"""Celery tasks — processing pipeline.

Fast-path:  process_article → embed inline → try_instant_event → scoring chain
Backfill:   compute_embedding_batch (batch catch-up), build_events (periodic sweep)
"""

import logging

from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
# FAST PATH — process + embed + instant event check (one chain, no waits)
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def process_article(self, news_id: int):
    """Clean → SimHash → NER → bucket → embed inline → try_instant_event."""
    try:
        return _run_async(_process_article_async(news_id))
    except Exception as exc:
        logger.exception("process_article failed for news_id=%s", news_id)
        raise self.retry(exc=exc, throw=False) from exc


async def _process_article_async(news_id: int) -> dict:
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import ArticleEntity, News, NewsClean
    from app.processing.bucket_classifier import get_bucket_classifier
    from app.processing.embedding_service import get_embedding
    from app.processing.freshness import is_fresh_enough
    from app.processing.ner_extractor import get_ner_extractor
    from app.processing.news_cleaner import NewsCleaner

    settings = get_settings()
    cleaner = NewsCleaner()
    # Singleton — instantiating NERExtractor() per task allocated a
    # fresh `en_core_web_lg` model (~750 MB resident) without
    # deterministically freeing the previous one. See the module
    # docstring on `app.processing.ner_extractor.get_ner_extractor`.
    ner = get_ner_extractor()
    classifier = get_bucket_classifier()

    async with async_session_factory() as session:
        news = (
            await session.execute(select(News).where(News.id == news_id))
        ).scalar_one_or_none()

        if not news:
            return {"status": "not_found", "news_id": news_id}

        if not is_fresh_enough(
            news.publish_date, news.ingestion_date,
            max_age_hours=settings.rss_max_article_age_hours,
        ):
            return {"status": "rejected_stale", "news_id": news_id}

        already = (
            await session.execute(
                select(NewsClean.id).where(NewsClean.news_id == news_id)
            )
        ).scalar_one_or_none()
        if already:
            return {"status": "already_processed", "news_id": news_id}

        raw_text = news.text or ""
        raw_title = news.title or ""
        cleaned = cleaner.clean_article({"title": raw_title, "content": raw_text})
        clean_text = cleaned.get("content", "")
        language = cleaned.get("language")
        word_count = cleaned.get("word_count", 0)

        title_words = len(raw_title.split())
        is_x_scraper = (news.source_name or "").startswith("x_scraper")
        min_wc = 8 if is_x_scraper else settings.min_word_count
        min_tw = 3 if is_x_scraper else settings.min_title_words
        if word_count < min_wc and title_words < min_tw:
            return {"status": "rejected_quality", "news_id": news_id}

        if language and language != "en":
            return {"status": "rejected_language", "news_id": news_id}

        simhash_val = _compute_simhash(clean_text)
        is_dup = await _check_simhash_dup(session, simhash_val, settings.clustering_simhash_threshold)
        if is_dup:
            return {"status": "rejected_duplicate", "news_id": news_id}

        text_for_classify = f"{raw_title} {clean_text[:500]}"
        bucket = classifier.predict(text_for_classify)

        text_for_ner = f"{raw_title}. {clean_text[:2000]}"
        entities = ner.extract_entities(text_for_ner)

        # Embed INLINE — no separate task, no batch wait
        from app.processing.text_composers import compose_news_v1, compose_news_v2
        composed_v1 = compose_news_v1(raw_title, clean_text)
        embedding = await get_embedding(composed_v1.text)

        # v2 inline write — best-effort; failure doesn't block news ingestion
        composed_v2 = compose_news_v2(raw_title, clean_text)
        embedding_v2 = None
        try:
            embedding_v2 = await get_embedding(composed_v2.text)
        except Exception as exc:
            logger.warning("news embedding_v2 compute failed news_id=%s: %s", news_id, exc)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        news_clean = NewsClean(
            news_id=news_id,
            clean_text=clean_text or raw_title,
            simhash=simhash_val,
            bucket=bucket,
            word_count=word_count,
            language=language or "en",
            embedding=embedding,
            embedding_computed_at=now if embedding else None,
            embedding_v2=embedding_v2,
            embedding_v2_composition=composed_v2.composition_version if embedding_v2 else None,
            embedding_v2_computed_at=now if embedding_v2 else None,
        )
        session.add(news_clean)
        await session.flush()

        seen_entities: set[tuple[str, str]] = set()
        for ent in entities:
            key = (ent["entity_type"], ent["entity_value"])
            if key in seen_entities:
                continue
            seen_entities.add(key)
            session.add(ArticleEntity(
                clean_id=news_clean.id,
                entity_type=ent["entity_type"],
                entity_value=ent["entity_value"],
            ))

        await session.commit()

    logger.info(
        "Processed news_id=%d → clean_id=%d bucket=%s embed=%s",
        news_id, news_clean.id, bucket, embedding is not None,
    )

    if embedding is not None:
        try_instant_event.apply_async(
            args=[news_clean.id], queue="scoring",
        )

    return {
        "status": "ok",
        "news_id": news_id,
        "clean_id": news_clean.id,
        "bucket": bucket,
        "embedded": embedding is not None,
    }


# ══════════════════════════════════════════════════════════════════════════
# FAST PATH — try to form an event instantly after embedding
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=1, default_retry_delay=5)
def try_instant_event(self, clean_id: int):
    """Find similar recent articles, create event if cluster ≥ min_articles,
    and dispatch scoring immediately. Eliminates the build_events batch wait."""
    try:
        return _run_async(_try_instant_event_async(clean_id))
    except Exception as exc:
        logger.exception("try_instant_event failed for clean_id=%s", clean_id)
        raise self.retry(exc=exc, throw=False) from exc


async def _try_instant_event_async(clean_id: int) -> dict:
    import numpy as np
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import Event, EventNewsLink, News, NewsClean
    from app.processing.freshness import is_fresh_enough

    settings = get_settings()

    async with async_session_factory() as session:
        anchor = (
            await session.execute(select(NewsClean).where(NewsClean.id == clean_id))
        ).scalar_one_or_none()
        if not anchor or anchor.embedding is None:
            return {"status": "no_anchor", "clean_id": clean_id}

        already_linked = (
            await session.execute(
                select(EventNewsLink.id).where(EventNewsLink.clean_id == clean_id)
            )
        ).scalar_one_or_none()
        if already_linked:
            return {"status": "already_linked", "clean_id": clean_id}

        # Find recent unlinked articles in the same bucket
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=settings.clustering_time_window_minutes
        )

        q = (
            select(NewsClean)
            .outerjoin(EventNewsLink)
            .where(
                EventNewsLink.id.is_(None),
                NewsClean.embedding.is_not(None),
                NewsClean.id != clean_id,
            )
        )

        candidates = (await session.execute(q.limit(200))).scalars().all()

        # Cosine similarity against anchor
        anchor_vec = np.array(anchor.embedding, dtype=np.float32)
        anchor_norm = np.linalg.norm(anchor_vec)
        if anchor_norm == 0:
            return {"status": "zero_embedding", "clean_id": clean_id}

        cluster_ids = [clean_id]
        cluster_articles = [anchor]

        for cand in candidates:
            cand_news = (
                await session.execute(select(News).where(News.id == cand.news_id))
            ).scalar_one_or_none()
            if cand_news and not is_fresh_enough(
                cand_news.publish_date, cand_news.ingestion_date,
                max_age_hours=float(settings.article_freshness_hours),
            ):
                continue

            cand_vec = np.array(cand.embedding, dtype=np.float32)
            cand_norm = np.linalg.norm(cand_vec)
            if cand_norm == 0:
                continue
            sim = float(np.dot(anchor_vec, cand_vec) / (anchor_norm * cand_norm))
            if sim >= settings.clustering_cosine_threshold:
                cluster_ids.append(cand.id)
                cluster_articles.append(cand)

        if len(cluster_ids) < settings.min_articles_per_event:
            return {
                "status": "insufficient_cluster",
                "clean_id": clean_id,
                "found": len(cluster_ids),
                "needed": settings.min_articles_per_event,
            }

        # Build consolidated event
        anchor_news = (
            await session.execute(select(News).where(News.id == anchor.news_id))
        ).scalar_one_or_none()

        sources = set()
        titles = []
        cluster_article_dates: list[tuple] = []
        for ca in cluster_articles:
            n = (await session.execute(select(News).where(News.id == ca.news_id))).scalar_one_or_none()
            if n:
                sources.add(n.source_name)
                titles.append(n.title)
                cluster_article_dates.append((n.publish_date, n.ingestion_date))

        event_title = titles[0] if titles else "Untitled event"
        event_summary = " | ".join(t[:200] for t in titles[:5])
        key_ents = []
        from app.db.models import ArticleEntity
        for cid in cluster_ids:
            ents = (await session.execute(
                select(ArticleEntity).where(ArticleEntity.clean_id == cid)
            )).scalars().all()
            for e in ents:
                key_ents.append(e.entity_value)
        key_ents = list(dict.fromkeys(key_ents))[:20]

        from app.processing.text_composers import compose_event_v1
        retrieval_text = compose_event_v1(event_title, event_summary, key_ents).text

        # Bug fix 2026-04-27: pre-fix, the fast path omitted first_seen /
        # last_seen so the DB `server_default=NOW()` kicked in and stale
        # tweets (publish_date 17 h ago) were treated as fresh, slipping
        # past `signal_event_max_age_hours = 6h` and emitting signals
        # on already-priced-in news.
        from app.processing.freshness import compute_event_seen_window
        first_seen, last_seen = compute_event_seen_window(cluster_article_dates)

        event = Event(
            event_title=event_title,
            event_summary=event_summary[:2000],
            event_retrieval_text=retrieval_text.strip(),
            key_entities=key_ents,
            event_type=anchor.bucket,
            bucket=anchor.bucket,
            articles_count=len(cluster_ids),
            unique_sources_count=len(sources),
            first_seen=first_seen,
            last_seen=last_seen,
            processing_status="new",
            embedding=None,
        )
        session.add(event)
        await session.flush()

        for cid in cluster_ids:
            session.add(EventNewsLink(event_id=event.id, clean_id=cid, role="supporting"))

        # Refresh counts from the live link set. The inline values above
        # match what recompute would compute today, but routing both paths
        # through the same helper means a future change to the cluster
        # construction can never silently desync stored vs live counts
        # (chantier-2 bug 3).
        from app.event_engine.event_counts import recompute_event_counts
        await session.flush()
        await recompute_event_counts(session, event_id=event.id)

        # LLM summarize if enabled
        if settings.event_llm_summarize and len(cluster_ids) >= settings.min_articles_per_event:
            try:
                from app.llm.event_summarizer import create_event_summarizer
                cluster_data = []
                for ca in cluster_articles:
                    n = (await session.execute(select(News).where(News.id == ca.news_id))).scalar_one_or_none()
                    cluster_data.append({
                        "title": n.title if n else "",
                        "clean_text": ca.clean_text,
                        "source_name": n.source_name if n else "",
                    })
                summarizer = create_event_summarizer()
                llm_result = await summarizer.summarize(cluster_data)
                if llm_result:
                    if llm_result.get("event_title"):
                        event.event_title = llm_result["event_title"]
                    if llm_result.get("event_summary"):
                        event.event_summary = llm_result["event_summary"]
                    ke = llm_result.get("key_entities")
                    if isinstance(ke, list) and ke:
                        event.key_entities = [str(x) for x in ke[:20]]
                    et = llm_result.get("event_type")
                    if et:
                        event.event_type = str(et)[:50]
                    from app.processing.text_composers import compose_event_v1
                    event.event_retrieval_text = compose_event_v1(
                        event.event_title,
                        event.event_summary or "",
                        list(event.key_entities or []),
                    ).text
                    event.embedding = None
            except Exception:
                logger.warning("LLM summarize failed for event %d, using heuristic", event.id)

        await session.commit()

        # Dispatch scoring immediately
        from app.workers.tasks_scoring import run_hybrid_search
        run_hybrid_search.apply_async(args=[event.id], queue="scoring")

    logger.info(
        "Instant event: clean_id=%d → event=%d (%d articles, %d sources)",
        clean_id, event.id, len(cluster_ids), len(sources),
    )
    return {
        "status": "event_created",
        "clean_id": clean_id,
        "event_id": event.id,
        "articles": len(cluster_ids),
    }


# ══════════════════════════════════════════════════════════════════════════
# BACKFILL — batch embedding (catch stragglers)
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def compute_embedding_batch(self, clean_ids: list[int] | None = None, limit: int = 200):
    """Batch-compute embeddings for news_clean rows still missing them."""
    try:
        return _run_async(_compute_embedding_batch_async(clean_ids, limit))
    except Exception as exc:
        logger.exception("compute_embedding_batch failed")
        raise self.retry(exc=exc, throw=False) from exc


async def _compute_embedding_batch_async(
    clean_ids: list[int] | None, limit: int,
) -> dict:
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import NewsClean
    from app.processing.embedding_service import get_embeddings

    async with async_session_factory() as session:
        if clean_ids:
            result = await session.execute(
                select(NewsClean).where(NewsClean.id.in_(clean_ids))
            )
        else:
            result = await session.execute(
                select(NewsClean)
                .where(NewsClean.embedding.is_(None))
                .order_by(NewsClean.id.desc())
                .limit(limit)
            )
        rows = result.scalars().all()

        if not rows:
            return {"status": "nothing_to_embed"}

        texts = [r.clean_text for r in rows]
        embeddings = await get_embeddings(texts)

        now = datetime.now(timezone.utc)
        embedded = 0
        newly_embedded_ids = []
        for row, emb in zip(rows, embeddings):
            if emb:
                row.embedding = emb
                row.embedding_computed_at = now
                embedded += 1
                newly_embedded_ids.append(row.id)

        await session.commit()

    for cid in newly_embedded_ids:
        try_instant_event.apply_async(args=[cid], queue="scoring")

    logger.info("Batch embedded %d / %d, dispatched instant-event checks", embedded, len(rows))
    return {"status": "ok", "embedded": embedded, "total": len(rows)}


# ══════════════════════════════════════════════════════════════════════════
# BACKFILL — periodic event sweep (catches articles not clustered by fast path)
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def build_events(self):
    """Cluster recent un-linked news_clean rows into events, then trigger scoring."""
    try:
        return _run_async(_build_events_async())
    except Exception as exc:
        logger.exception("build_events failed")
        raise self.retry(exc=exc, throw=False) from exc


async def _build_events_async() -> dict:
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import ArticleEntity, EventNewsLink, News, NewsClean
    from app.event_engine.event_builder import build_event_from_cluster
    from app.event_engine.simple_clusterer import create_simple_clusterer
    from app.processing.embedding_reader import get_active_embedding
    from app.processing.freshness import is_fresh_enough

    settings = get_settings()
    clusterer = create_simple_clusterer()

    async with async_session_factory() as session:
        result = await session.execute(
            select(NewsClean)
            .outerjoin(EventNewsLink)
            .where(
                EventNewsLink.id.is_(None),
                NewsClean.embedding.is_not(None),
            )
            .order_by(NewsClean.id.desc())
            .limit(300)
        )
        unlinked = result.scalars().all()

        if not unlinked:
            return {"status": "no_new_articles"}

        articles_data = []
        for nc in unlinked:
            news = (
                await session.execute(select(News).where(News.id == nc.news_id))
            ).scalar_one_or_none()
            ents = (
                await session.execute(
                    select(ArticleEntity).where(ArticleEntity.clean_id == nc.id)
                )
            ).scalars().all()

            articles_data.append({
                "clean_id": nc.id,
                "title": news.title if news else "",
                "clean_text": nc.clean_text,
                "bucket": nc.bucket,
                "source_name": news.source_name if news else "",
                "publish_date": news.publish_date if news else None,
                "ingestion_date": news.ingestion_date if news else None,
                "embedding": (lambda v: list(v) if v is not None else None)(get_active_embedding(nc, "news")),
                "entities": [
                    {"entity_type": e.entity_type, "entity_value": e.entity_value}
                    for e in ents
                ],
            })

        articles_data = [
            a for a in articles_data
            if is_fresh_enough(
                a.get("publish_date"), a.get("ingestion_date"),
                max_age_hours=float(settings.article_freshness_hours),
            )
        ]

        articles_with_emb = [a for a in articles_data if a.get("embedding") is not None]
        clusters = clusterer.cluster_articles(articles_with_emb)

        events_created = 0
        for cluster in clusters:
            if not cluster or len(cluster) < settings.min_articles_per_event:
                continue

            event, clean_ids = build_event_from_cluster(cluster)
            session.add(event)
            await session.flush()

            if settings.event_llm_summarize:
                try:
                    from app.llm.event_summarizer import create_event_summarizer
                    summarizer = create_event_summarizer()
                    llm_result = await summarizer.summarize(cluster)
                    if llm_result:
                        if llm_result.get("event_title"):
                            event.event_title = llm_result["event_title"]
                        if llm_result.get("event_summary"):
                            event.event_summary = llm_result["event_summary"]
                        ke = llm_result.get("key_entities")
                        if isinstance(ke, list) and ke:
                            event.key_entities = [str(x) for x in ke[:20]]
                        et = llm_result.get("event_type")
                        if et:
                            event.event_type = str(et)[:50]
                        from app.processing.text_composers import compose_event_v1
                        event.event_retrieval_text = compose_event_v1(
                            event.event_title,
                            event.event_summary or "",
                            list(event.key_entities or []),
                        ).text
                        event.embedding = None
                    await session.flush()
                except Exception:
                    logger.warning("LLM summarize failed for event %d", event.id)

            for cid in clean_ids:
                session.add(EventNewsLink(event_id=event.id, clean_id=cid, role="supporting"))

            # Refresh counts from the live link set (chantier-2 bug 3).
            from app.event_engine.event_counts import recompute_event_counts
            await session.flush()
            await recompute_event_counts(session, event_id=event.id)

            events_created += 1

            from app.workers.tasks_scoring import run_hybrid_search
            run_hybrid_search.apply_async(args=[event.id], queue="scoring")

        await session.commit()

    logger.info("build_events (backfill): %d articles → %d events", len(articles_data), events_created)
    return {"status": "ok", "articles": len(articles_data), "events_created": events_created}


# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════

def _compute_simhash(text: str) -> int | None:
    if not text or len(text) < 20:
        return None
    try:
        from simhash import Simhash
        val = Simhash(text).value
        if val >= (1 << 63):
            val -= (1 << 64)
        return val
    except Exception:
        return None


async def _check_simhash_dup(session, simhash_val: int | None, threshold: float) -> bool:
    if simhash_val is None:
        return False

    from sqlalchemy import select

    from app.db.models import NewsClean

    result = await session.execute(
        select(NewsClean.simhash)
        .where(NewsClean.simhash.is_not(None))
        .order_by(NewsClean.id.desc())
        .limit(500)
    )
    existing_hashes = [row[0] for row in result.fetchall()]

    max_hamming = max(3, int(64 * threshold))
    for existing in existing_hashes:
        if existing is None:
            continue
        hamming = bin(simhash_val ^ existing).count("1")
        if hamming <= max_hamming:
            return True

    return False
