"""Immutable scoring context passed to every baseline function.

Baselines must not hit the DB — all data they need lives here. This guarantees
deterministic, fast (<1ms) execution and makes unit testing trivial.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


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


async def build_scoring_context(
    *,
    signal_id: int,
    market_id: str,
    event_id: int | None,
    market_price: float,
    articles: list[dict[str, Any]] | None,
    t0: datetime,
    market_price_24h_ago: float | None = None,
) -> ScoringContext:
    """Assemble a ScoringContext from whatever the signal builder has on hand.

    `market_price_24h_ago` is an explicit input — chantier #1 ships with None
    (graceful degradation; momentum becomes a no-op). A future chantier can
    wire it to Polymarket /prices-history without touching the scoring flow.

    `articles` is the list of raw article dicts the builder already holds.
    Only items with a direction hint + source_weight participate in
    news_sentiment; the rest are ignored.
    """
    impacts: list[ArticleImpact] = []
    for art in (articles or []):
        d = (art.get("direction_hint") or art.get("direction") or "NEUTRAL").upper()
        if d not in ("YES", "NO", "NEUTRAL"):
            d = "NEUTRAL"
        w_raw = art.get("source_weight")
        try:
            w = float(w_raw) if w_raw is not None else 0.5
        except (TypeError, ValueError):
            w = 0.5
        impacts.append(ArticleImpact(direction=d, source_weight=w))

    return ScoringContext(
        signal_id=signal_id,
        market_id=market_id,
        event_id=event_id,
        market_price=market_price,
        market_price_24h_ago=market_price_24h_ago,
        article_impacts=tuple(impacts),
        t0=t0,
    )
