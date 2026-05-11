"""World News API client — async, returns article dicts ready for DB insertion."""

import logging
from datetime import UTC, datetime, timedelta

import httpx
from dateutil import parser as date_parser

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

BASE_URL = "https://api.worldnewsapi.com"
FETCH_TIMEOUT = 30.0

CATEGORIES = "politics,business,science,technology,environment,entertainment"

_quota_backoff_until: datetime | None = None


async def fetch_top_news(limit: int = 50) -> list[dict]:
    """Fetch top English-language news from World News API.

    Returns enriched article dicts with keys:
        url, title, text, source_name, source_tier, source_weight,
        publish_date, ingestion_lag_seconds
    """
    global _quota_backoff_until

    api_key = settings.worldnews_api_key
    if not api_key:
        logger.warning("worldnews_api_key not set — skipping")
        return []

    now = datetime.now(UTC)

    if _quota_backoff_until and now < _quota_backoff_until:
        logger.info("World News API quota backoff until %s — skipping", _quota_backoff_until.isoformat())
        return []

    earliest = (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")

    try:
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT) as client:
            resp = await client.get(
                f"{BASE_URL}/search-news",
                params={
                    "language": "en",
                    "source-countries": "us,gb,ca,au",
                    "sort": "publish-time",
                    "sort-direction": "DESC",
                    "earliest-publish-date": earliest,
                    "number": limit,
                    "categories": CATEGORIES,
                },
                headers={"x-api-key": api_key},
            )
            if resp.status_code == 402:
                _quota_backoff_until = now + timedelta(hours=1)
                logger.warning("World News API quota exhausted (402). Backing off for 1 hour until %s", _quota_backoff_until.isoformat())
                return []
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.error("World News API HTTP error: %s", e)
        return []
    except Exception as e:
        logger.error("World News API request failed: %s", e)
        return []

    _quota_backoff_until = None

    articles: list[dict] = []
    for raw in data.get("news", []):
        url = (raw.get("url") or "").strip()
        title = (raw.get("title") or "").strip()
        if not url or not title:
            continue

        text = raw.get("text") or raw.get("summary") or ""
        pub_date = _parse_date(raw.get("publish_date"))

        lag = None
        if pub_date:
            lag = max(0, int((now - pub_date).total_seconds()))

        articles.append({
            "url": url,
            "title": title,
            "text": text,
            "source_name": f"WorldNews:{raw.get('source_country', 'unknown')}",
            "source_tier": 2,
            "source_weight": 0.70,
            "publish_date": pub_date,
            "ingestion_lag_seconds": lag,
        })

    logger.info("World News API returned %d articles", len(articles))
    return articles


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = date_parser.parse(str(raw))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, OverflowError):
        return None
