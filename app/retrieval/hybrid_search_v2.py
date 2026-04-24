"""Hybrid search v2 — v1 + date-proximity + bucket-match.

The main entry point `hybrid_search_markets_v2` is defined in task 5.
This module lands in two steps so the pure helpers can be TDD'd first.
"""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.retrieval.bm25_index import BM25Index
import app.retrieval.vector_retriever as _vector_retriever

logger = logging.getLogger(__name__)


def date_proximity(
    market_end_date: Optional[datetime],
    event_last_seen: datetime,
    tau_days: float,
) -> float:
    """Exponential decay past a 7-day floor; 0 if the market is already past.

    Returns 1.0 when the market ends within 7 days of the event, then decays
    as exp(-(days_until - 7) / tau_days). Returns 0.0 when end_date is None
    or already past.
    """
    if market_end_date is None:
        return 0.0
    days_until = (market_end_date - event_last_seen).total_seconds() / 86400.0
    if days_until < 0:
        return 0.0
    if days_until <= 7.0:
        return 1.0
    if tau_days <= 0:
        return 0.0
    return math.exp(-(days_until - 7.0) / tau_days)


def bucket_match(market_bucket: Optional[str], event_bucket: Optional[str]) -> float:
    """1.0 iff both are the same real bucket; 0.0 for None/other/mismatch."""
    if event_bucket is None or event_bucket == "other":
        return 0.0
    if market_bucket is None:
        return 0.0
    return 1.0 if market_bucket == event_bucket else 0.0


def _count_entity_matches(question: str, entities: list[str]) -> int:
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


async def hybrid_search_markets_v2(
    session: AsyncSession,
    event_embedding: list[float],
    event_text: str,
    top_k: Optional[int] = None,
    event_bucket: Optional[str] = None,
    event_entities: Optional[list[str]] = None,
    event_last_seen: Optional[datetime] = None,
) -> list[dict]:
    """Run hybrid search v2:
      RRF(vec, bm25) + w_entity*entity_matches
                     + w_date*date_proximity
                     + w_bucket*bucket_match
    """
    settings = get_settings()
    k = top_k or settings.top_k_markets
    rrf_k = settings.ranking_v2_rrf_k
    w_entity = settings.ranking_v2_w_entity
    w_date = settings.ranking_v2_w_date
    w_bucket = settings.ranking_v2_w_bucket
    tau_days = settings.ranking_v2_tau_days
    min_sim = settings.ranking_v2_min_sim

    vector_results = await _vector_retriever.search_markets_by_embedding(
        session, event_embedding, limit=k * 3, min_sim=min_sim,
    )
    if not vector_results:
        logger.info("hybrid_search_v2: empty vector pool")
        return []

    bm25 = BM25Index()
    bm25.build_index(vector_results, text_field="market_retrieval_text")
    bm25_results = bm25.search(event_text, limit=k * 3)

    vec_rank = {r["market_id"]: i for i, r in enumerate(vector_results)}
    bm25_rank: dict[str, int] = {}
    bm25_score_map: dict[str, float] = {}
    for r in bm25_results:
        mid = r.get("market_id")
        if mid:
            bm25_rank[mid] = r.get("bm25_rank", len(bm25_results)) - 1
            bm25_score_map[mid] = r.get("bm25_score", 0.0)

    all_ids = set(vec_rank.keys()) | set(bm25_rank.keys())
    market_map = {r["market_id"]: r for r in vector_results}
    entities = event_entities or []

    fused: list[dict] = []
    for mid in all_ids:
        vr = vec_rank.get(mid, k * 3)
        br = bm25_rank.get(mid, k * 3)
        rrf_score = (1.0 / (rrf_k + vr + 1)) + (1.0 / (rrf_k + br + 1))

        entry = market_map.get(mid, {}).copy()
        entry["market_id"] = mid
        entry["bm25_score"] = bm25_score_map.get(mid, 0.0)

        question = entry.get("question") or ""
        n_ent = _count_entity_matches(question, entities)
        if n_ent > 0:
            rrf_score += n_ent * w_entity
            entry["entity_matches"] = n_ent

        # date proximity — requires event_last_seen to be meaningful
        if event_last_seen is not None and w_date > 0:
            dp = date_proximity(entry.get("end_date"), event_last_seen, tau_days)
            if dp > 0:
                rrf_score += dp * w_date
                entry["date_proximity"] = dp

        # bucket match
        if w_bucket > 0:
            mkt_bucket = entry.get("bucket")
            bm = bucket_match(mkt_bucket, event_bucket)
            if bm > 0:
                rrf_score += bm * w_bucket
                entry["bucket_match"] = True

        entry["rrf_score"] = round(rrf_score, 6)
        fused.append(entry)

    fused.sort(key=lambda x: x["rrf_score"], reverse=True)
    for i, entry in enumerate(fused[:k]):
        entry["rank"] = i + 1

    logger.info("hybrid_search_v2: %d candidates → top %d", len(fused), k)
    return fused[:k]
