"""Four deterministic, zero-LLM baseline predictors.

Every baseline takes a ScoringContext and returns a VariantPrediction. Must be
pure (no DB, no network, no wall-clock dependency beyond ctx.t0).
"""

from __future__ import annotations

import math
import random as _random

from app.measurement.scoring_context import ScoringContext
from app.measurement.variant_registry import VariantPrediction


def baseline_random(ctx: ScoringContext) -> VariantPrediction:
    """Coin flip keyed by signal_id. Deterministic across runs."""
    rng = _random.Random(ctx.signal_id)
    direction = "BUY_YES" if rng.random() < 0.5 else "BUY_NO"
    return VariantPrediction(direction=direction, probability=0.5)


def baseline_market_price(ctx: ScoringContext) -> VariantPrediction:
    """Follow the market: BUY_YES if price > 0.5, else BUY_NO. Prob = market price."""
    direction = "BUY_YES" if ctx.market_price > 0.5 else "BUY_NO"
    return VariantPrediction(direction=direction, probability=ctx.market_price)


def baseline_momentum(ctx: ScoringContext) -> VariantPrediction:
    """24h momentum. None if we lack a 24h-ago price."""
    if ctx.market_price_24h_ago is None:
        return VariantPrediction(direction=None, probability=None)
    return_24h = ctx.market_price - ctx.market_price_24h_ago  # in [-1, 1]
    direction = "BUY_YES" if return_24h > 0 else "BUY_NO"
    prob = max(0.01, min(0.99, 0.5 + 0.5 * return_24h))
    return VariantPrediction(direction=direction, probability=prob)


def baseline_news_sentiment(ctx: ScoringContext) -> VariantPrediction:
    """Weighted sentiment of attached articles. ABSTAIN (None, None) when:
      - no articles
      - total source-weight is zero
      - sentiment is exactly zero (all NEUTRAL or perfectly balanced)

    Audit 2026-04-25 P1.1: previously fell into the `sentiment > 0` branch
    when sentiment was 0, emitting a fake (BUY_NO, 0.5) prediction that
    didn't reflect news content. The prod path doesn't yet supply
    per-article direction labels, so every cluster's articles defaulted to
    NEUTRAL — every prod news_sentiment row was that fake BUY_NO @ 0.5,
    polluting cross-baseline Brier comparisons. Honest abstention until
    per-article direction is wired upstream.
    """
    if not ctx.article_impacts:
        return VariantPrediction(direction=None, probability=None)

    def _sign(d: str) -> float:
        if d == "YES":
            return 1.0
        if d == "NO":
            return -1.0
        return 0.0

    weighted = sum(_sign(a.direction) * a.source_weight for a in ctx.article_impacts)
    total_weight = sum(a.source_weight for a in ctx.article_impacts)
    if total_weight == 0:
        return VariantPrediction(direction=None, probability=None)

    sentiment = weighted / total_weight                     # in [-1, 1]
    if sentiment == 0:
        # No directional information — abstain rather than fake BUY_NO.
        return VariantPrediction(direction=None, probability=None)
    prob = 1.0 / (1.0 + math.exp(-2.0 * sentiment))         # sigmoid spread
    direction = "BUY_YES" if sentiment > 0 else "BUY_NO"
    return VariantPrediction(direction=direction, probability=prob)
