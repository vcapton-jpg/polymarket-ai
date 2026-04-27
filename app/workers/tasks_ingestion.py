"""Celery tasks — ingestion layer (markets + news sources).

Phase 1: fetch_markets, compute_market_percentiles  (implemented)
Phase 2: fetch_rss_feeds, fetch_worldnews           (implemented)
"""

import logging
from datetime import datetime, timezone

from app.ingestion.gdelt_client import GdeltClient
from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

import re

_BOILERPLATE_RE = re.compile(
    r"(?i)("
    r"this market will resolve\b.*?(?:\.\s*|\n|$)"
    r"|if the results? (?:is|are) not known\b.*?(?:\.\s*|\n|$)"
    r"|if there is ambiguity\b.*?(?:\.\s*|\n|$)"
    r"|this market (?:pertains to|includes|covers)\b.*?(?:\.\s*|\n|$)"
    r")"
)


def _build_retrieval_text(mkt: dict) -> str:
    """Build embedding-ready text from a market dict (thin wrapper around v1 composer)."""
    from app.processing.text_composers import compose_market_v1
    return compose_market_v1(mkt).text


# ══════════════════════════════════════════════════════════════════════════
# Phase 1 — Markets
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, soft_time_limit=1800, time_limit=1860)
def fetch_markets(self):
    """Fetch all active markets from Gamma, enrich via CLOB, compute embeddings, persist."""
    try:
        return _run_async(_fetch_markets_async())
    except Exception as exc:
        logger.exception("fetch_markets failed")
        raise self.retry(exc=exc)


async def _fetch_markets_async() -> dict:

    from sqlalchemy import select

    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import Market
    from app.polymarket.clob_client import ClobClient
    from app.polymarket.gamma_client import GammaClient

    gamma = GammaClient()
    clob = ClobClient()

    try:
        raw_markets = await gamma.fetch_all_active_markets()
        logger.info("Gamma returned %d markets", len(raw_markets))

        created = 0
        updated = 0
        BATCH_SIZE = 100

        for i in range(0, len(raw_markets), BATCH_SIZE):
            batch = raw_markets[i : i + BATCH_SIZE]
            async with async_session_factory() as session:
                for mkt in batch:
                    market_id = mkt["market_id"]

                    retrieval_text = _build_retrieval_text(mkt)
                    mkt["market_retrieval_text"] = retrieval_text

                    existing = (
                        await session.execute(
                            select(Market).where(Market.market_id == market_id)
                        )
                    ).scalar_one_or_none()

                    if existing:
                        _update_market(existing, mkt)
                        updated += 1
                    else:
                        new_market = Market(
                            market_id=market_id,
                            question=mkt["question"],
                            description=mkt.get("description"),
                            category=mkt.get("category"),
                            tags=mkt.get("tags"),
                            end_date=_parse_date(mkt.get("end_date")),
                            active=mkt.get("active", True),
                            closed=mkt.get("closed", False),
                            accepting_orders=mkt.get("accepting_orders", True),
                            volume=mkt.get("volume"),
                            volume_24h=mkt.get("volume_24h"),
                            liquidity=mkt.get("liquidity"),
                            best_bid=mkt.get("best_bid"),
                            best_ask=mkt.get("best_ask"),
                            spread=mkt.get("spread"),
                            last_trade_price=mkt.get("last_trade_price"),
                            clob_token_ids=mkt.get("clob_token_ids"),
                            image_url=mkt.get("image_url"),
                            market_retrieval_text=retrieval_text,
                        )
                        session.add(new_market)
                        created += 1

                await session.commit()
            logger.info("Markets batch %d-%d committed (%d/%d)", i, i + len(batch), created + updated, len(raw_markets))

        await _compute_market_embeddings()

        enriched = await _enrich_top_markets_clob(clob)

        result = {"status": "ok", "created": created, "updated": updated, "clob_enriched": enriched}
        logger.info("fetch_markets: %s", result)
        return result

    finally:
        await gamma.close()
        await clob.close()


async def _enrich_top_markets_clob(clob) -> int:
    """CLOB-enrich only markets that have embeddings (used in matching) — not all 50K."""
    import asyncio

    from sqlalchemy import select

    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import Market

    async with async_session_factory() as session:
        result = await session.execute(
            select(Market)
            .where(
                Market.embedding.is_not(None),
                Market.active.is_(True),
                Market.closed.is_(False),
            )
            .order_by(Market.updated_at.asc().nullslast())
            .limit(500)
        )
        markets = result.scalars().all()

        if not markets:
            return 0

        enriched = 0
        for m in markets:
            try:
                clob_data = await clob.enrich_market(m.market_id)
                if clob_data.get("volume") is not None:
                    m.volume = clob_data["volume"]
                if clob_data.get("liquidity") is not None:
                    m.liquidity = clob_data["liquidity"]
                if clob_data.get("best_bid") is not None:
                    m.best_bid = clob_data["best_bid"]
                if clob_data.get("best_ask") is not None:
                    m.best_ask = clob_data["best_ask"]
                if clob_data.get("last_trade_price") is not None:
                    m.last_trade_price = clob_data["last_trade_price"]
                enriched += 1
            except Exception:
                pass
            await asyncio.sleep(0.05)

        await session.commit()
        logger.info("CLOB-enriched %d / %d markets with embeddings", enriched, len(markets))
        return enriched


def _update_market(existing, data: dict):
    existing.active = data.get("active", existing.active)
    existing.closed = data.get("closed", existing.closed)
    existing.accepting_orders = data.get("accepting_orders", existing.accepting_orders)
    existing.volume = data.get("volume") or existing.volume
    existing.volume_24h = data.get("volume_24h") or existing.volume_24h
    existing.liquidity = data.get("liquidity") or existing.liquidity
    existing.best_bid = data.get("best_bid") or existing.best_bid
    existing.best_ask = data.get("best_ask") or existing.best_ask
    existing.spread = data.get("spread") or existing.spread
    existing.last_trade_price = data.get("last_trade_price") or existing.last_trade_price
    # Backfill image_url for markets ingested before image capture was wired
    # (Bug: 0/135k markets had image_url, all signal cards rendered no
    # thumbnail). Use `or` so we never overwrite a populated URL with None
    # if Gamma transiently omits the field.
    existing.image_url = data.get("image_url") or existing.image_url
    new_text = data.get("market_retrieval_text")
    if new_text and new_text != existing.market_retrieval_text:
        existing.market_retrieval_text = new_text
        existing.embedding = None


async def _compute_market_embeddings():
    from sqlalchemy import func, select, text

    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import Market
    from app.processing.embedding_service import get_embedding, get_embeddings

    BATCH = 2000
    total_computed = 0

    async with async_session_factory() as session:
        pending_count = (
            await session.execute(
                select(func.count())
                .select_from(Market)
                .where(Market.embedding.is_(None), Market.market_retrieval_text.is_not(None))
            )
        ).scalar() or 0

    if pending_count == 0:
        return

    logger.info("Market embeddings: %d markets pending", pending_count)

    while True:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Market)
                .where(Market.embedding.is_(None))
                .where(Market.market_retrieval_text.is_not(None))
                .limit(BATCH)
            )
            markets = result.scalars().all()

            if not markets:
                break

            texts = [m.market_retrieval_text for m in markets]
            embeddings = await get_embeddings(texts)

            from datetime import datetime, timezone

            from app.processing.text_composers import compose_market_v2

            computed = 0
            for market, emb in zip(markets, embeddings):
                if emb:
                    market.embedding = emb
                    computed += 1

                # v2 inline write — compute in this same loop to amortize session I/O
                try:
                    composed_v2 = compose_market_v2({
                        "question": market.question,
                        "description": market.description,
                        "tags": market.tags,
                        "category": market.category,
                    })
                    emb_v2 = await get_embedding(composed_v2.text)
                except Exception as exc:
                    logger.warning(
                        "market embedding_v2 failed market_id=%s: %s",
                        market.market_id, exc,
                    )
                    emb_v2 = None
                if emb_v2:
                    market.embedding_v2 = emb_v2
                    market.embedding_v2_composition = composed_v2.composition_version
                    market.embedding_v2_computed_at = datetime.now(timezone.utc)

            await session.commit()
            total_computed += computed
            logger.info("Market embeddings: batch done %d (total %d / %d)", computed, total_computed, pending_count)

    logger.info("Market embeddings: completed %d total", total_computed)

    if total_computed > 0:
        from app.db.database import engine as _engine

        async with _engine.connect() as conn:
            await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.execute(text("REINDEX INDEX CONCURRENTLY idx_markets_embedding_hnsw"))
        logger.info("Market embeddings: HNSW index rebuilt after %d updates", total_computed)


# ══════════════════════════════════════════════════════════════════════════
# Phase 1 — Percentiles daily job
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=1)
def compute_market_percentiles(self):
    """Recompute liquidity_pct and volume_24h_pct across active markets."""
    try:
        return _run_async(_compute_percentiles_async())
    except Exception as exc:
        logger.exception("compute_market_percentiles failed")
        raise self.retry(exc=exc)


async def _compute_percentiles_async() -> dict:
    from sqlalchemy import select

    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import Market

    async with async_session_factory() as session:
        result = await session.execute(
            select(Market).where(Market.active.is_(True), Market.closed.is_(False))
        )
        markets = result.scalars().all()

        if not markets:
            return {"status": "no_markets"}

        liquidities = sorted(
            [float(m.liquidity) for m in markets if m.liquidity is not None]
        )
        volumes = sorted(
            [float(m.volume_24h) for m in markets if m.volume_24h is not None]
        )

        for m in markets:
            if m.liquidity is not None and liquidities:
                m.liquidity_pct = _percentile_rank(float(m.liquidity), liquidities)
            if m.volume_24h is not None and volumes:
                m.volume_24h_pct = _percentile_rank(float(m.volume_24h), volumes)

        await session.commit()

    logger.info("Percentiles computed for %d markets", len(markets))
    return {"status": "ok", "markets": len(markets)}


def _percentile_rank(value: float, sorted_values: list[float]) -> float:
    if not sorted_values:
        return 0.0
    count_below = sum(1 for v in sorted_values if v < value)
    return round(count_below / len(sorted_values), 4)


# ══════════════════════════════════════════════════════════════════════════
# Phase 2 — RSS feeds (Tier 1 + X/Twitter via RSSHub)
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def fetch_rss_feeds(self):
    """Poll tier-2 and tier-3 RSS + X_RSS sources at the slow cadence
    (`rss_poll_interval_seconds`, default 90 s). Tier-1 wire sources are
    polled separately by `fetch_rss_tier1` at a faster cadence — see
    that task's docstring for the latency reasoning.
    """
    try:
        return _run_async(_fetch_rss_async(tiers=(2, 3)))
    except Exception as exc:
        logger.exception("fetch_rss_feeds failed")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def fetch_rss_tier1(self):
    """Poll TIER-1 RSS + X_RSS sources at the fast cadence
    (`tier1_rss_poll_interval_seconds`, default 15 s).

    Why a dedicated task: lag audit on 7 days of @Reuters / @FirstSquawk /
    @business / @AP showed publish→ingestion p50 = 4-24 min and p95 up
    to 17 h. The dominant contributor was the 90 s poll interval combined
    with RSSHub's 60 s cache TTL — a tweet that landed in the cache just
    after a poll could wait 90 s for the next pickup. Polling tier-1 at
    15 s aligns with the cache TTL so a fresh tweet reaches us within
    one cache-window cycle. Tier-2/3 stay at 90 s to avoid over-fetching.
    """
    try:
        return _run_async(_fetch_rss_async(tiers=(1,)))
    except Exception as exc:
        logger.exception("fetch_rss_tier1 failed")
        raise self.retry(exc=exc)


async def _fetch_rss_async(*, tiers: tuple[int, ...] = (1, 2, 3)) -> dict:
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import News
    from app.ingestion.rss_scraper import fetch_sources
    from app.ingestion.sources_registry import get_sources_by_tier_and_type
    from app.processing.freshness import is_fresh_enough

    settings = get_settings()
    sources = await get_sources_by_tier_and_type(tiers, ("rss", "x_rss"))
    if not sources:
        logger.warning("No RSS/X_RSS sources found in DB for tiers=%s", tiers)
        return {"status": "no_sources", "tiers": list(tiers)}

    articles = await fetch_sources(sources)

    inserted = 0
    duplicates = 0
    skipped_stale = 0
    new_ids: list[int] = []

    async with async_session_factory() as session:
        for art in articles:
            url = art["url"]
            if not is_fresh_enough(
                art.get("publish_date"),
                None,
                max_age_hours=settings.rss_max_article_age_hours,
            ):
                skipped_stale += 1
                continue
            exists = (
                await session.execute(
                    select(News.id).where(News.url == url)
                )
            ).scalar_one_or_none()

            if exists:
                duplicates += 1
                continue

            source_id = art.get("source_id") or await _resolve_or_create_source(
                session,
                art["source_name"],
                source_type="rss_auto",
                tier=int(art.get("source_tier", 3)),
                weight=float(art.get("source_weight", 0.4)),
            )
            news_row = News(
                url=url,
                title=art["title"],
                text=art.get("text"),
                source_name=art["source_name"],
                source_id=source_id,
                source_tier=art["source_tier"],
                source_weight=art["source_weight"],
                publish_date=art.get("publish_date"),
                ingestion_lag_seconds=art.get("ingestion_lag_seconds"),
            )
            session.add(news_row)
            await session.flush()
            new_ids.append(news_row.id)
            inserted += 1

        await session.commit()

    _dispatch_processing(new_ids)

    result = {
        "status": "ok",
        "fetched": len(articles),
        "inserted": inserted,
        "duplicates": duplicates,
        "skipped_stale": skipped_stale,
    }
    logger.info("fetch_rss_feeds: %s", result)
    return result


# ══════════════════════════════════════════════════════════════════════════
# Phase 2 — World News API (Tier 2)
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_worldnews(self):
    """Poll World News API, persist new articles, trigger processing."""
    try:
        return _run_async(_fetch_worldnews_async())
    except Exception as exc:
        logger.exception("fetch_worldnews failed")
        raise self.retry(exc=exc)


async def _fetch_worldnews_async() -> dict:
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import News
    from app.ingestion.worldnews_client import fetch_top_news
    from app.processing.freshness import is_fresh_enough

    settings = get_settings()
    articles = await fetch_top_news(limit=50)

    inserted = 0
    duplicates = 0
    new_ids: list[int] = []

    async with async_session_factory() as session:
        for art in articles:
            url = art["url"]
            if not is_fresh_enough(
                art.get("publish_date"),
                None,
                max_age_hours=settings.rss_max_article_age_hours,
            ):
                continue
            exists = (
                await session.execute(
                    select(News.id).where(News.url == url)
                )
            ).scalar_one_or_none()

            if exists:
                duplicates += 1
                continue

            source_id = await _resolve_or_create_source(
                session,
                art["source_name"],
                source_type="worldnews_auto",
                tier=int(art.get("source_tier", 3)),
                weight=float(art.get("source_weight", 0.4)),
            )
            news_row = News(
                url=url,
                title=art["title"],
                text=art.get("text"),
                source_name=art["source_name"],
                source_id=source_id,
                source_tier=art["source_tier"],
                source_weight=art["source_weight"],
                publish_date=art.get("publish_date"),
                ingestion_lag_seconds=art.get("ingestion_lag_seconds"),
            )
            session.add(news_row)
            await session.flush()
            new_ids.append(news_row.id)
            inserted += 1

        await session.commit()

    _dispatch_processing(new_ids)

    result = {
        "status": "ok",
        "fetched": len(articles),
        "inserted": inserted,
        "duplicates": duplicates,
    }
    logger.info("fetch_worldnews: %s", result)
    return result


# ══════════════════════════════════════════════════════════════════════════
# 𝕏-scraper inbox — JSON/CSV drops (https://fmoncomble.github.io/X-scraper/)
# ══════════════════════════════════════════════════════════════════════════


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def ingest_x_scraper_inbox(self):
    """Import files from x_scraper_inbox_dir, enqueue process_article, move to processed."""
    try:
        return _run_async(_ingest_x_scraper_inbox_async())
    except Exception as exc:
        logger.exception("ingest_x_scraper_inbox failed")
        raise self.retry(exc=exc)


async def _ingest_x_scraper_inbox_async() -> dict:
    import shutil
    import time
    from pathlib import Path

    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.database import get_session_factory
    from app.db.models import News
    from app.ingestion.x_scraper_import import load_articles_from_file

    settings = get_settings()
    if settings.x_scraper_inbox_interval_seconds <= 0:
        return {"status": "disabled"}

    inbox = Path(settings.x_scraper_inbox_dir)
    if not inbox.is_absolute():
        inbox = Path.cwd() / inbox
    processed = Path(settings.x_scraper_processed_dir)
    if not processed.is_absolute():
        processed = Path.cwd() / processed

    if not inbox.is_dir():
        return {"status": "no_inbox", "path": str(inbox)}

    processed.mkdir(parents=True, exist_ok=True)
    async_session_factory = get_session_factory()

    files_processed = 0
    rows_inserted = 0
    all_new_ids: list[int] = []

    for pattern in ("*.json", "*.csv"):
        for path in sorted(inbox.glob(pattern)):
            if not path.is_file():
                continue
            try:
                articles = load_articles_from_file(path)
            except Exception as e:
                logger.warning("Skip %s: %s", path, e)
                continue

            new_ids: list[int] = []
            async with async_session_factory() as session:
                for art in articles:
                    url = art["url"]
                    exists = (
                        await session.execute(select(News.id).where(News.url == url))
                    ).scalar_one_or_none()
                    if exists:
                        continue
                    now = datetime.now(timezone.utc)
                    lag = None
                    if art.get("publish_date"):
                        lag = int((now - art["publish_date"]).total_seconds())
                        if lag < 0:
                            lag = 0
                    news_row = News(
                        url=url,
                        title=art["title"],
                        text=art.get("text"),
                        source_name=art["source_name"][:255],
                        source_tier=art["source_tier"],
                        source_weight=art["source_weight"],
                        publish_date=art.get("publish_date"),
                        ingestion_lag_seconds=lag,
                    )
                    session.add(news_row)
                    await session.flush()
                    new_ids.append(news_row.id)
                    rows_inserted += 1

                await session.commit()

            _dispatch_processing(new_ids)
            all_new_ids.extend(new_ids)

            dest = processed / path.name
            if dest.exists():
                dest = processed / f"{path.stem}_{int(time.time())}{path.suffix}"
            shutil.move(str(path), str(dest))
            files_processed += 1

    logger.info(
        "ingest_x_scraper_inbox: files=%d rows=%d",
        files_processed,
        rows_inserted,
    )
    return {
        "status": "ok",
        "files_processed": files_processed,
        "inserted": rows_inserted,
        "dispatched": len(all_new_ids),
    }


# ══════════════════════════════════════════════════════════════════════════
# Shared helpers
# ══════════════════════════════════════════════════════════════════════════

def _dispatch_processing(news_ids: list[int]):
    """Fire process_article tasks for newly ingested articles."""
    from app.workers.tasks_pipeline import process_article

    for nid in news_ids:
        process_article.apply_async(
            args=[nid],
            queue="pipeline",
        )
    if news_ids:
        logger.info("Dispatched %d process_article tasks", len(news_ids))


def _parse_date(val) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        from dateutil.parser import parse as parse_dt
        return parse_dt(str(val))
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════
# Phase 3 — GDELT 2.0 (Tier 3, auto-source-registry)
# ══════════════════════════════════════════════════════════════════════════

async def _resolve_or_create_source(
    session,
    source_name: str,
    *,
    source_type: str = "gdelt_auto",
    tier: int = 3,
    weight: float = 0.4,
) -> int:
    from sqlalchemy import select

    from app.db.models import SourceRegistry

    row = (await session.execute(
        select(SourceRegistry).where(SourceRegistry.source_name == source_name)
    )).scalar_one_or_none()
    if row:
        return row.id
    row = SourceRegistry(
        source_name=source_name,
        tier=tier,
        weight=weight,
        active=True,
        source_type=source_type,
        url=f"https://{source_name}",
    )
    session.add(row)
    await session.flush()
    logger.info(
        "sources_registry: auto-created source '%s' (type=%s)",
        source_name, source_type,
    )
    return row.id


async def _fetch_gdelt_async(queries: list[str] | None = None) -> int:
    """Run one GDELT ingestion pass. Returns count of inserted news rows."""
    from sqlalchemy import select

    from app.db.database import get_session_factory
    from app.db.models import News, SourceRegistry

    async_session_factory = get_session_factory()
    client = GdeltClient()
    inserted = 0

    async with async_session_factory() as s:
        if queries is None:
            rows = (await s.execute(
                select(SourceRegistry).where(
                    SourceRegistry.source_type == "gdelt_query",
                    SourceRegistry.active.is_(True),
                )
            )).scalars().all()
            queries = [r.source_name for r in rows] or ["trump", "fomc", "ceasefire", "crypto regulation"]

        for q in queries:
            try:
                arts = await client.fetch_recent(q, timespan="15min")
            except Exception as e:
                logger.exception("GDELT fetch failed for %r: %s", q, e)
                continue

            for a in arts:
                exists = (await s.execute(
                    select(News.id).where(News.url == a["url"])
                )).scalar_one_or_none()
                if exists:
                    continue
                source_id = await _resolve_or_create_source(s, a["source_name"])
                n = News(
                    url=a["url"],
                    title=a["title"],
                    text=a.get("text", ""),
                    source_name=a["source_name"],
                    source_tier=3,
                    source_weight=0.4,
                    source_id=source_id,
                    publish_date=a["publish_date"],
                )
                s.add(n)
                inserted += 1
        await s.commit()

    logger.info("fetch_gdelt: inserted=%d across queries=%d", inserted, len(queries))
    return inserted


@celery_app.task(name="app.workers.tasks_ingestion.fetch_gdelt")
def fetch_gdelt() -> int:
    return _run_async(_fetch_gdelt_async())
