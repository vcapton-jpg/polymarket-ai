"""Vector retriever using pgvector cosine distance."""

import logging
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
) -> list[dict]:
    """Search for active, non-closed markets with the closest embeddings.

    Bucket filter is intentionally removed — the full market corpus is searched
    to avoid hiding niche markets behind noisy bucket classification.
    """
    if event_embedding is None:
        return []

    col = active_column_name("market")
    embedding_str = "[" + ",".join(str(x) for x in event_embedding) + "]"

    params: dict = {
        "embedding": embedding_str,
        "limit": limit,
        "min_sim": MIN_COSINE_SIMILARITY,
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
