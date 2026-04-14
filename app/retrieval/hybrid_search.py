"""Hybrid search — BM25 + pgvector cosine + RRF fusion + entity boost."""

import logging
import re
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.retrieval.bm25_index import BM25Index
from app.retrieval.vector_retriever import search_markets_by_embedding

logger = logging.getLogger(__name__)

ENTITY_BOOST_PER_MATCH = 0.5


def _count_entity_matches(question: str, entities: list[str]) -> int:
    """Count how many event entities appear in a market question (case-insensitive)."""
    if not question or not entities:
        return 0
    q_lower = question.lower()
    matches = 0
    for ent in entities:
        if len(ent) < 2:
            continue
        if re.search(r"\b" + re.escape(ent.lower()) + r"\b", q_lower):
            matches += 1
    return matches


async def hybrid_search_markets(
    session: AsyncSession,
    event_embedding: list[float],
    event_text: str,
    top_k: Optional[int] = None,
    event_bucket: Optional[str] = None,
    event_entities: Optional[list[str]] = None,
) -> list[dict]:
    """Run hybrid search: vector retrieval → BM25 re-rank → RRF fusion → entity boost."""
    settings = get_settings()
    k = top_k or settings.top_k_markets
    rrf_k = settings.rrf_k

    vector_results = await search_markets_by_embedding(
        session, event_embedding, limit=k * 3,
    )

    if not vector_results:
        logger.info("Hybrid search: no markets above cosine similarity threshold")
        return []

    bm25 = BM25Index()
    bm25.build_index(vector_results, text_field="market_retrieval_text")
    bm25_results = bm25.search(event_text, limit=k * 3)

    vec_rank = {r["market_id"]: i for i, r in enumerate(vector_results)}
    bm25_rank = {}
    bm25_score_map = {}
    for r in bm25_results:
        mid = r.get("market_id")
        if mid:
            bm25_rank[mid] = r.get("bm25_rank", len(bm25_results)) - 1
            bm25_score_map[mid] = r.get("bm25_score", 0.0)

    all_ids = set(vec_rank.keys()) | set(bm25_rank.keys())
    fused: list[dict] = []

    market_map = {r["market_id"]: r for r in vector_results}

    entities = event_entities or []

    for mid in all_ids:
        vr = vec_rank.get(mid, k * 3)
        br = bm25_rank.get(mid, k * 3)
        rrf_score = (1.0 / (rrf_k + vr + 1)) + (1.0 / (rrf_k + br + 1))

        entry = market_map.get(mid, {}).copy()
        entry["market_id"] = mid
        entry["bm25_score"] = bm25_score_map.get(mid, 0.0)

        if entities:
            question = entry.get("question") or ""
            matches = _count_entity_matches(question, entities)
            if matches > 0:
                rrf_score += matches * ENTITY_BOOST_PER_MATCH
                entry["entity_matches"] = matches

        entry["rrf_score"] = round(rrf_score, 6)
        fused.append(entry)

    fused.sort(key=lambda x: x["rrf_score"], reverse=True)

    for i, entry in enumerate(fused[:k]):
        entry["rank"] = i + 1

    entity_boosted = sum(1 for e in fused[:k] if e.get("entity_matches", 0) > 0)
    logger.info(
        "Hybrid search: %d candidates → top %d (%d entity-boosted)",
        len(fused), k, entity_boosted,
    )
    return fused[:k]
