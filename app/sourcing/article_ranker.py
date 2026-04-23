"""Pure article ranker — composite score of cosine similarity + recency decay.

No I/O: takes candidates + market embedding + t0, returns a ranked list.
Deterministic tie-break: newer publish_date wins, then lower news_clean_id.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable


@dataclass(frozen=True)
class RankedArticle:
    news_clean_id: int
    rank: int
    score: float
    cosine: float
    recency_weight: float
    excerpt: str | None = None


def _cosine(a: list[float] | None, b: list[float] | None) -> float:
    """Dot-product similarity, clipped to [0, 1].

    Embeddings are *assumed* unit-normalized (pgvector stores them this way
    after the ingestion pipeline normalises via text-embedding-3-small).
    For unit vectors, dot-product == cosine similarity, so we skip the
    sqrt-division — it's a no-op on normalized vectors and avoids distorting
    magnitude when callers pass non-unit test vectors.
    """
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return max(0.0, dot)


def _recency_weight(t0: datetime, publish_date: datetime, tau_hours: float) -> float:
    delta_hours = max(0.0, (t0 - publish_date).total_seconds() / 3600.0)
    return math.exp(-delta_hours / tau_hours)


class ArticleRanker:
    """Composite ranker: score = clip(α·cosine + β·recency_w, 0, 1)."""

    def __init__(self, *, alpha: float, beta: float, tau_hours: float) -> None:
        if tau_hours <= 0:
            raise ValueError("tau_hours must be > 0")
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.tau_hours = float(tau_hours)

    @classmethod
    def from_settings(cls, settings) -> "ArticleRanker":
        return cls(
            alpha=settings.sourcing_alpha,
            beta=settings.sourcing_beta,
            tau_hours=settings.sourcing_recency_tau_hours,
        )

    def rank(
        self,
        pool: Iterable[dict[str, Any]],
        market_embedding: list[float] | None,
        t0: datetime,
        *,
        top_k: int,
    ) -> list[RankedArticle]:
        """Return up to `top_k` articles ranked by composite score.

        Articles without an embedding are dropped. If `market_embedding` is
        None, falls back to pure recency (cosine = 0 for every candidate).
        """
        scored: list[tuple[float, datetime, int, float, float, dict]] = []
        for art in pool:
            emb = art.get("embedding")
            if emb is None:
                continue
            cos = _cosine(emb, market_embedding) if market_embedding is not None else 0.0
            pd = art.get("publish_date")
            if pd is None:
                # Missing publish_date: treat as infinitely old.
                rw = 0.0
            else:
                rw = _recency_weight(t0, pd, self.tau_hours)
            raw = self.alpha * cos + self.beta * rw
            score = max(0.0, min(1.0, raw))
            scored.append((score, pd or datetime.min, int(art["news_clean_id"]), cos, rw, art))

        # Sort: score DESC, publish_date DESC (newer wins tie), news_clean_id ASC (deterministic).
        scored.sort(key=lambda t: (-t[0], -(t[1].timestamp() if t[1] != datetime.min else 0.0), t[2]))

        out: list[RankedArticle] = []
        for rank, (score, _pd, ncid, cos, rw, _art) in enumerate(scored[:top_k], start=1):
            out.append(RankedArticle(
                news_clean_id=ncid,
                rank=rank,
                score=score,
                cosine=cos,
                recency_weight=rw,
                excerpt=None,
            ))
        return out
