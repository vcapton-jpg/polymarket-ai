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


async def fetch_sources(sources: list[dict]) -> list[dict]:
    """Fetch articles from multiple source dicts (from sources_registry).

    Each source dict has: source_name, source_type, url, tier, weight.
    Returns enriched article dicts ready for DB insertion.

    Performance contract — single shared `httpx.AsyncClient` across the
    whole batch (audit M10, 2026-05-05). Pre-PR, every `fetch_feed`
    call opened its own client; with `fetch_rss_tier1` running every
    15 s over ~50 feeds that meant ~50 TLS handshakes per task. The
    shared client keeps connection pooling across same-host fetches
    (RSSHub serves Twitter mirrors from one origin) and amortises the
    handshake. On distinct origins the cost is identical to before, so
    there is no regression.
    """
    now = datetime.now(timezone.utc)
    all_articles: list[dict] = []

    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT, follow_redirects=True,
    ) as client:
        for src in sources:
            try:
                raw = await fetch_feed(src["url"], client=client)
                for article in raw:
                    lag = None
                    if article["publish_date"]:
                        lag = int((now - article["publish_date"]).total_seconds())
                        if lag < 0:
                            lag = 0

                    all_articles.append({
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
            except Exception as e:
                logger.error("Error fetching %s: %s", src["source_name"], e)

    logger.info("Total articles fetched from %d sources: %d", len(sources), len(all_articles))
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
