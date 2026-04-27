"""Sources registry — load active sources from DB, cache in memory."""

import logging

from sqlalchemy import select

from app.db.database import get_session_factory
from app.db.models import SourceRegistry

logger = logging.getLogger(__name__)

_sources_cache: dict[str, dict] = {}


async def load_sources() -> list[dict]:
    """Load all active sources from DB into cache. Returns list of source dicts."""
    global _sources_cache
    _sources_cache.clear()

    async with get_session_factory()() as session:
        result = await session.execute(
            select(SourceRegistry).where(SourceRegistry.active.is_(True))
        )
        rows = result.scalars().all()

    sources = []
    for row in rows:
        entry = {
            "id": row.id,
            "source_name": row.source_name,
            "source_type": row.source_type,
            "url": row.url,
            "tier": row.tier,
            "weight": row.weight,
        }
        _sources_cache[row.source_name] = entry
        sources.append(entry)

    logger.info("Loaded %d active sources from DB", len(sources))
    return sources


async def get_sources_by_type(*source_types: str) -> list[dict]:
    """Return cached sources filtered by source_type (e.g. 'rss', 'x_rss', 'api').

    Reloads from DB if cache is empty.
    """
    if not _sources_cache:
        await load_sources()

    return [
        s for s in _sources_cache.values()
        if s["source_type"] in source_types
    ]


async def get_sources_by_tier_and_type(
    tiers: tuple[int, ...],
    source_types: tuple[str, ...],
) -> list[dict]:
    """Filter cached sources by both tier set and source_type set.

    Used by the split-cadence ingestion: tier-1 sources poll every
    `tier1_rss_poll_interval_seconds` (default 15 s) for low publish→signal
    latency on the wire-grade accounts; tier-2/3 stay on the slower
    `rss_poll_interval_seconds` (default 90 s) cadence to avoid
    over-fetching the upstream feeds.
    """
    if not _sources_cache:
        await load_sources()

    return [
        s for s in _sources_cache.values()
        if s["source_type"] in source_types and s["tier"] in tiers
    ]


def get_source_weight(source_name: str) -> dict | None:
    """Get cached source info by name. Returns None if not found."""
    return _sources_cache.get(source_name)


def get_source_tier(source_name: str) -> int:
    """Get source tier by name. Defaults to 2 if unknown."""
    info = _sources_cache.get(source_name)
    return info["tier"] if info else 2
