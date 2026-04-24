"""Feature-flag dispatcher for the event→market hybrid search.

Routes callers to either `hybrid_search.hybrid_search_markets` (v1, frozen)
or `hybrid_search_v2.hybrid_search_markets_v2` (v2, tuned) based on the
`ranking_variant_event_to_market` setting.

Callers should always use `hybrid_search_markets_dispatch(...)` — never
import v1/v2 directly in production code. (Tests may import them for
bit-exact comparison.)
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_VALID_VARIANTS = ("v1", "v2")


def active_ranking_variant() -> str:
    """Return 'v1' or 'v2'. Any other value falls back to 'v1'."""
    v = getattr(get_settings(), "ranking_variant_event_to_market", "v1")
    return v if v in _VALID_VARIANTS else "v1"


async def hybrid_search_markets_dispatch(
    session: AsyncSession,
    event_embedding: list[float],
    event_text: str,
    top_k: Optional[int] = None,
    event_bucket: Optional[str] = None,
    event_entities: Optional[list[str]] = None,
    event_last_seen=None,
) -> list[dict]:
    """Route to v1 or v2 based on the active ranking variant."""
    variant = active_ranking_variant()
    if variant == "v2":
        from app.retrieval.hybrid_search_v2 import hybrid_search_markets_v2
        return await hybrid_search_markets_v2(
            session, event_embedding, event_text,
            top_k=top_k,
            event_bucket=event_bucket,
            event_entities=event_entities,
            event_last_seen=event_last_seen,
        )
    from app.retrieval.hybrid_search import hybrid_search_markets
    return await hybrid_search_markets(
        session, event_embedding, event_text,
        top_k=top_k,
        event_bucket=event_bucket,
        event_entities=event_entities,
    )
