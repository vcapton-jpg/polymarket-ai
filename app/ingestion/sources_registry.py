"""Sources registry management."""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SourceRegistry

logger = logging.getLogger(__name__)

# Default sources when database is not available
DEFAULT_SOURCES = {
    "reuters": {"name": "Reuters", "tier": 1, "weight": 1.0},
    "ap": {"name": "AP", "tier": 1, "weight": 1.0},
    "afp": {"name": "AFP", "tier": 1, "weight": 1.0},
    "bbc": {"name": "BBC", "tier": 1, "weight": 1.0},
    "guardian": {"name": "Guardian", "tier": 1, "weight": 0.9},
    "nyt": {"name": "NYT", "tier": 1, "weight": 0.9},
    "washpost": {"name": "Washington Post", "tier": 1, "weight": 0.9},
    "cnn": {"name": "CNN", "tier": 2, "weight": 0.7},
    "fox": {"name": "Fox News", "tier": 2, "weight": 0.6},
    "breitbart": {"name": "Breitbart", "tier": 2, "weight": 0.5},
    "huffpost": {"name": "HuffPost", "tier": 2, "weight": 0.6},
}

# In-memory cache for source weights
_source_weights: dict[str, dict] = {}


async def init_sources_registry(db: AsyncSession) -> None:
    """Initialize sources registry from database.

    Args:
        db: Database session.
    """
    global _source_weights

    try:
        result = await db.execute(select(SourceRegistry))
        sources = result.scalars().all()

        if sources:
            for source in sources:
                _source_weights[source.name.lower()] = {
                    "weight": source.weight,
                    "tier": source.tier,
                    "active": source.active,
                }
            logger.info(f"Loaded {len(sources)} sources from database")
        else:
            # Use defaults if database is empty
            for name, info in DEFAULT_SOURCES.items():
                _source_weights[name] = {
                    "weight": info["weight"],
                    "tier": info["tier"],
                    "active": True,
                }
            logger.info("Using default sources registry")
    except Exception as e:
        logger.warning(f"Could not load sources from database: {e}")
        # Use defaults
        for name, info in DEFAULT_SOURCES.items():
            _source_weights[name] = {
                "weight": info["weight"],
                "tier": info["tier"],
                "active": True,
            }


def get_source_weight(source_name: str) -> Optional[dict]:
    """Get source weight by name.

    Args:
        source_name: Name of the source.

    Returns:
        Dictionary with weight, tier, and active status, or None if not found.
    """
    return _source_weights.get(source_name.lower())


def get_source_tier(source_name: str) -> int:
    """Get source tier by name.

    Args:
        source_name: Name of the source.

    Returns:
        Tier level (1, 2, or 3).
    """
    info = get_source_weight(source_name)
    return info["tier"] if info else 2


async def add_source(
    db: AsyncSession,
    name: str,
    url: str,
    tier: int,
    weight: float = 1.0,
) -> SourceRegistry:
    """Add a new source to the registry.

    Args:
        db: Database session.
        name: Source name.
        url: Source URL.
        tier: Tier level (1, 2, or 3).
        weight: Source weight.

    Returns:
        Created SourceRegistry instance.
    """
    source = SourceRegistry(name=name, url=url, tier=tier, weight=weight, active=True)
    db.add(source)
    await db.commit()
    await db.refresh(source)

    # Update cache
    _source_weights[name.lower()] = {"weight": weight, "tier": tier, "active": True}

    return source


async def deactivate_source(db: AsyncSession, name: str) -> bool:
    """Deactivate a source.

    Args:
        db: Database session.
        name: Source name.

    Returns:
        True if deactivated, False if not found.
    """
    source = await db.get(SourceRegistry, name)
    if source:
        source.active = False
        await db.commit()

        # Update cache
        if name.lower() in _source_weights:
            _source_weights[name.lower()]["active"] = False

        return True
    return False