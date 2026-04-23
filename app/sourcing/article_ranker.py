"""Pure article ranker — composite score of cosine similarity + recency decay.

Zero I/O: takes candidates + market embedding + t0, returns a ranked list.
Fully unit-testable. Task 4 ships just the `RankedArticle` dataclass; the
ranker class lands in Task 5.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RankedArticle:
    """Result of ranking one candidate.

    Immutable so Celery can serialize batches safely. `excerpt` is None at
    ranking time — it's filled later if the LLM returns an excerpt matching
    this news_clean_id. Kept on this dataclass so the persistence layer has
    one value object to write.
    """
    news_clean_id: int
    rank: int               # 1-based; 1 = top
    score: float            # composite in [0, 1]
    cosine: float           # raw cosine, clipped to [0, 1]
    recency_weight: float   # exp decay, [0, 1]
    excerpt: str | None = None
