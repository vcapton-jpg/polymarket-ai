"""Immutable scoring context passed to every baseline function.

Baselines must not hit the DB — all data they need lives here. This guarantees
deterministic, fast (<1ms) execution and makes unit testing trivial.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ArticleImpact:
    """One news source's contribution to news_sentiment baseline."""
    direction: str          # 'YES' | 'NO' | 'NEUTRAL'
    source_weight: float    # [0, 1]


@dataclass(frozen=True)
class ScoringContext:
    signal_id: int
    market_id: str
    event_id: int | None
    market_price: float                     # P(YES) at signal time, [0, 1]
    market_price_24h_ago: float | None      # P(YES) 24h ago, or None if unknown
    article_impacts: tuple[ArticleImpact, ...]
    t0: datetime                            # signal creation time (UTC)
