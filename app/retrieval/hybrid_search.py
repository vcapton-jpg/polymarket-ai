"""Hybrid search combining vector and BM25."""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.bm25_index import create_bm25_index
from app.retrieval.vector_retriever import create_vector_retriever

logger = logging.getLogger(__name__)

# RRF constant
RRF_K = 60


class HybridSearch:
    """Hybrid search using RRF fusion."""

    def __init__(self, db: AsyncSession):
        """Initialize hybrid search.

        Args:
            db: Database session.
        """
        self.db = db
        self.vector_retriever = create_vector_retriever(db)
        self.bm25_index = create_bm25_index()

    async def search_markets(
        self,
        event_embedding: list[float],
        event_text: str,
        limit: int = 10,
        db_session: Optional[AsyncSession] = None,
    ) -> list[dict]:
        """Search for markets using hybrid search.

        Args:
            event_embedding: Event embedding.
            event_text: Event text for BM25.
            limit: Maximum results.
            db_session: Database session (optional, uses self.db if not provided).

        Returns:
            List of market candidates with scores.
        """
        results = []

        # Get vector results
        vector_results = await self.vector_retriever.search_similar_markets(
            event_embedding,
            limit=limit * 2,
        )

        # Build BM25 index from vector results
        if vector_results:
            self.bm25_index.build_index(vector_results, "question")
            bm25_results = self.bm25_index.search(event_text, limit=limit * 2)

            # Merge rankings
            vector_ranks = {r["market_id"]: i for i, r in enumerate(vector_results)}
            bm25_ranks = {
                r["market_id"]: r["bm25_rank"]
                for r in bm25_results
                if "market_id" in r
            }

            # RRF fusion
            for doc in vector_results + bm25_results:
                if "market_id" not in doc:
                    continue

                market_id = doc["market_id"]
                vec_rank = vector_ranks.get(market_id, limit)
                bm_rank = bm25_ranks.get(market_id, limit)

                # RRF score
                rrf_score = (1 / (RRF_K + vec_rank + 1)) + (
                    1 / (RRF_K + bm_rank + 1)
                )

                if market_id in [r.get("market_id") for r in results]:
                    # Update existing
                    for r in results:
                        if r.get("market_id") == market_id:
                            r["rrf_score"] = max(rrf_score, r.get("rrf_score", 0))
                            break
                else:
                    doc["rrf_score"] = rrf_score
                    results.append(doc)

            # Sort by RRF score
            results.sort(key=lambda r: r.get("rrf_score", 0), reverse=True)

        return results[:limit]


async def create_hybrid_search(db: AsyncSession) -> HybridSearch:
    """Create a hybrid search instance.

    Args:
        db: Database session.

    Returns:
        Configured HybridSearch.
    """
    return HybridSearch(db)