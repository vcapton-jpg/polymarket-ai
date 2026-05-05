"""Async RSS fetcher — handles standard RSS feeds and X/Twitter via RSSHub.

Pulls source URLs from sources_registry (DB), not from hardcoded lists.
Both 'rss' and 'x_rss' source types use feedparser under the hood.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import feedparser
import httpx
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)

FETCH_TIMEOUT = 20.0
_USER_AGENT = "PolymarketSignalBot/1.0"


async def fetch_feed(
    url: str,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> list[dict]:
    """Fetch and parse a single RSS feed URL.

    `client` is optional — if provided, the caller owns its lifecycle
    (use this when fetching many feeds in a row to avoid re-doing TLS
    handshake on every URL). When `None` we open a one-shot client for
    backward compat with single-call sites.

    Returns a list of raw article dicts with keys:
        url, title, text, publish_date
    """
    try:
        if client is None:
            async with httpx.AsyncClient(
                timeout=FETCH_TIMEOUT, follow_redirects=True,
            ) as own_client:
                resp = await own_client.get(url, headers={"User-Agent": _USER_AGENT})
                resp.raise_for_status()
                raw_xml = resp.text
        else:
            resp = await client.get(url, headers={"User-Agent": _USER_AGENT})
            resp.raise_for_status()
            raw_xml = resp.text
    except Exception as e:
        logger.warning("HTTP error fetching %s: %s", url, e)
        return []

    feed = feedparser.parse(raw_xml)
    articles: list[dict] = []

    for entry in feed.entries:
        link = entry.get("link", "").strip()
        title = entry.get("title", "").strip()
        if not link or not title:
            continue

        content = _extract_content(entry)
        publish_date = _parse_publish_date(entry)

        articles.append({
            "url": link,
            "title": title,
            "text": content,
            "publish_date": publish_date,
        })

    return articles


# Cap on the number of in-flight RSS fetches per task. 50 sources at
# once is fine on a fat broadband link; below that the bottleneck stops
# being TCP and starts being the upstream feeds. Tune via
# `RSS_FETCH_CONCURRENCY` env var if needed (e.g. on a constrained VPS).
import os

_FETCH_CONCURRENCY = int(os.environ.get("RSS_FETCH_CONCURRENCY", "20"))


async def _fetch_one_source(
    src: dict,
    *,
    client: httpx.AsyncClient,
    now: datetime,
    semaphore: "asyncio.Semaphore",
) -> list[dict]:
    """Fetch + enrich one source. Acquires the shared semaphore so the
    total in-flight count stays bounded even when the source list is
    large. Errors are logged and swallowed — one bad feed must not abort
    the batch."""
    async with semaphore:
        try:
            raw = await fetch_feed(src["url"], client=client)
        except Exception as e:
            logger.error("Error fetching %s: %s", src["source_name"], e)
            return []

    enriched: list[dict] = []
    for article in raw:
        lag = None
        if article["publish_date"]:
            lag = int((now - article["publish_date"]).total_seconds())
            if lag < 0:
                lag = 0
        enriched.append({
            "url": article["url"],
            "title": article["title"],
            "text": article["text"],
            "source_name": src["source_name"],
            "source_id": src.get("id"),
            "source_tier": src["tier"],
            "source_weight": src["weight"],
            "publish_date": article["publish_date"],
            "ingestion_lag_seconds": lag,
        })

    logger.info(
        "Fetched %d articles from %s (%s)",
        len(raw), src["source_name"], src["source_type"],
    )
    return enriched


async def fetch_sources(sources: list[dict]) -> list[dict]:
    """Fetch articles from multiple source dicts (from sources_registry).

    Each source dict has: source_name, source_type, url, tier, weight.
    Returns enriched article dicts ready for DB insertion.

    Performance contract — concurrent fetches via `asyncio.gather` with
    a bounded semaphore (`RSS_FETCH_CONCURRENCY`, default 20). Audit
    follow-up 2026-05-05:

      Pre-PR the loop was sequential (`for src in sources: await
      fetch_feed(...)`) which meant ~64 s per `fetch_rss_tier1` task on
      50 sources at ~1.3 s each. Beat enqueues `fetch_rss_tier1` every
      15 s, so even with 4 replicas the queue grew without bound
      (observed: 2025 → 2964 → 2966 → 2971 in 90 s).

      With concurrency 20, the same 50-source batch finishes in
      ~ceil(50 / 20) × p95_per_fetch ≈ 6-8 s. That's an 8-10× speedup
      on the wall clock for one task — combined with the 4 replicas,
      the throughput ceiling jumps from ~1 to ~30+ tasks/min, well
      above beat's enqueue rate.

      Errors stay isolated: each source is fetched in its own coroutine
      with its own try/except, so one bad RSS feed timing out does not
      block the other 49.

      Connection pooling preserved — the shared `httpx.AsyncClient` is
      handed to every coroutine, and httpx's internal connection pool
      keeps keep-alive across same-host fetches (most RSSHub mirrors
      hit the same origin).
    """
    import asyncio

    now = datetime.now(timezone.utc)
    semaphore = asyncio.Semaphore(_FETCH_CONCURRENCY)

    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT, follow_redirects=True,
    ) as client:
        results = await asyncio.gather(
            *(
                _fetch_one_source(src, client=client, now=now, semaphore=semaphore)
                for src in sources
            ),
            return_exceptions=False,  # _fetch_one_source already swallows
        )

    all_articles: list[dict] = [a for batch in results for a in batch]
    logger.info(
        "Total articles fetched from %d sources: %d (concurrency=%d)",
        len(sources), len(all_articles), _FETCH_CONCURRENCY,
    )
    return all_articles


# ── helpers ───────────────────────────────────────────────────────────────


def _extract_content(entry) -> str:
    """Pull the best text from a feedparser entry."""
    content = ""
    if hasattr(entry, "content") and entry.content:
        content = entry.content[0].get("value", "")
    elif hasattr(entry, "summary"):
        content = entry.summary
    elif hasattr(entry, "description"):
        content = entry.description

    if content:
        soup = BeautifulSoup(content, "lxml")
        content = soup.get_text(separator=" ", strip=True)

    return content


def _parse_publish_date(entry) -> Optional[datetime]:
    """Parse publish date from a feedparser entry, returning timezone-aware UTC."""
    for field in ("published", "updated", "created"):
        raw = getattr(entry, field, None)
        if raw:
            try:
                dt = date_parser.parse(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, OverflowError):
                continue
    return None
