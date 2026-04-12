"""Vector retriever using pgvector."""

import logging
from typing import Optional

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class VectorRetriever:
    """Retriever using vector similarity search."""

    def __init__(self, db: AsyncSession):
        """Initialize the vector retriever.

        Args:
            db: Database session.
        """
        self.db = db

    async def search_similar_markets(
        self,
        event_embedding: list[float],
        limit: int = 10,
    ) -> list[dict]:
        """Search for similar markets using vector similarity.

        Args:
            event_embedding: Event embedding vector.
            limit: Maximum number of results.

        Returns:
            List of market dictionaries with similarity scores.
        """
        if not event_embedding:
            return []

        # Convert embedding to string format for PostgreSQL
        embedding_str = "[" + ",".join(str(x) for x in event_embedding) + "]"

        try:
            query = text("""
                SELECT
                    id,
                    market_id,
                    question,
                    category,
                    end_date,
                    liquidity,
                    volume_24h,
                    best_bid,
                    best_ask,
                    1 - (embedding <=> :embedding::vector) AS similarity
                FROM markets
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> :embedding::vector
                LIMIT :limit
            """)

            result = await self.db.execute(
                query,
                {"embedding": embedding_str, "limit": limit},
            )

            rows = result.fetchall()

            return [
                {
                    "id": row[0],
                    "market_id": row[1],
                    "question": row[2],
                    "category": row[3],
                    "end_date": row[4],
                    "liquidity": row[5],
                    "volume_24h": row[6],
                    "best_bid": row[7],
                    "best_ask": row[8],
                    "cosine_similarity": row[9],
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []


def create_vector_retriever(db: AsyncSession) -> VectorRetriever:
    """Create a vector retriever instance.

    Args:
        db: Database session.

    Returns:
        Configured VectorRetriever.
    """
    return VectorRetriever(db)