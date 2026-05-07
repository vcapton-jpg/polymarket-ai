"""Vector retriever using pgvector cosine distance."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.processing.embedding_reader import active_column_name

logger = logging.getLogger(__name__)


MIN_COSINE_SIMILARITY = 0.45


async def search_markets_by_embedding(
    session: AsyncSession,
    event_embedding: list[float],
    limit: int = 20,
    event_bucket: Optional[str] = None,
    min_sim: Optional[float] = None,
    *,
    # Pre-filter at the same Filter A thresholds enforced post-LLM in
    # `app/workers/tasks_scoring.py:_market_quality_reject` so the vector
    # probe doesn't waste work on candidates that will be rejected after
    # we've already paid the LLM bill on them. Audit 2026-05-06: 70 % of
    # post-vector candidates failed Filter A volume/liquidity/price; the
    # cost was wasted vector ranking + wasted LLM analyses on rejects.
    # Defaults MUST stay in sync with the Filter A constants (currently
    # MIN_VOLUME_24H_USD=250, MIN_LIQUIDITY_USD=2000, RESOLVED_PRICE 0.03/0.97
    # and settings.market_min_remaining_hours=48) — pass `min_volume_24h=0`
    # etc. to disable pre-filter for shadow runs.
    min_volume_24h: float = 250.0,
    min_liquidity: float = 2000.0,
    price_low: float = 0.03,
    price_high: float = 0.97,
    min_remaining_hours: int = 48,
) -> list[dict]:
    """Search for active, non-closed markets with the closest embeddings.

    Bucket filter is intentionally removed — the full market corpus is searched
    to avoid hiding niche markets behind noisy bucket classification.

    `min_sim` lets callers (notably hybrid_search_v2) override the cosine-
    similarity floor; when omitted the module-level `MIN_COSINE_SIMILARITY`
    is used so v1 behavior is preserved exactly.
    """
    if event_embedding is None:
        return []

    col = active_column_name("market")
    embedding_str = "[" + ",".join(str(x) for x in event_embedding) + "]"

    effective_min_sim = MIN_COSINE_SIMILARITY if min_sim is None else min_sim
    end_date_min = datetime.now(timezone.utc) + timedelta(hours=min_remaining_hours)

    params: dict = {
        "embedding": embedding_str,
        "limit": limit,
        "min_sim": effective_min_sim,
        "min_volume": min_volume_24h,
        "min_liquidity": min_liquidity,
        "price_low": price_low,
        "price_high": price_high,
        "end_date_min": end_date_min,
    }

    try:
        result = await session.execute(
            text(f"""
                SELECT
                    market_id,
                    question,
                    category,
                    bucket,
                    end_date,
                    liquidity,
                    volume_24h,
                    best_bid,
                    best_ask,
                    spread,
                    last_trade_price,
                    market_retrieval_text,
                    1 - ({col} <=> cast(:embedding as vector)) AS cosine_score
                FROM markets
                WHERE {col} IS NOT NULL
                  AND active = true
                  AND closed = false
                  AND coalesce(volume_24h, 0) >= :min_volume
                  AND coalesce(liquidity, 0) >= :min_liquidity
                  AND (last_trade_price IS NULL OR last_trade_price BETWEEN :price_low AND :price_high)
                  AND (end_date IS NULL OR end_date > :end_date_min)
                  AND 1 - ({col} <=> cast(:embedding as vector)) >= :min_sim
                ORDER BY {col} <=> cast(:embedding as vector)
                LIMIT :limit
            """),
            params,
        )

        rows = result.fetchall()
        return [
            {
                "market_id": r[0],
                "question": r[1],
                "category": r[2],
                "bucket": r[3],
                "end_date": r[4],
                "liquidity": r[5],
                "volume_24h": r[6],
                "best_bid": r[7],
                "best_ask": r[8],
                "spread": r[9],
                "last_trade_price": r[10],
                "market_retrieval_text": r[11],
                "cosine_score": float(r[12]) if r[12] else 0.0,
            }
            for r in rows
        ]

    except Exception as e:
        logger.error("Vector search failed: %s", e)
        return []
