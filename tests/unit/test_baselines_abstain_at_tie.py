"""Audit follow-up [P1]: `baseline_market_price` and `baseline_momentum`
must ABSTAIN on the equality boundary, not invent a fake `BUY_NO @ 0.5`.

Background: same family as the P1.1 news_sentiment bug.
- baseline_market_price falls into the `> 0.5` test → BUY_NO when price
  is exactly 0.5 (currently 13 prod rows). At that price the market has
  no directional signal; emitting BUY_NO is dishonest.
- baseline_momentum falls into the `> 0` test → BUY_NO when return_24h
  is exactly 0. Currently masked because all 312 momentum rows are
  abstained for missing token-id, but the bug surfaces the moment
  /prices-history works.

Fix mirrors the P1.1 pattern: abstain (None, None) on the tie.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.measurement.baselines import baseline_market_price, baseline_momentum
from app.measurement.scoring_context import ArticleImpact, ScoringContext


def _ctx(*, market_price: float, market_price_24h_ago: float | None = None):
    return ScoringContext(
        signal_id=1, market_id="m", event_id=1,
        market_price=market_price,
        market_price_24h_ago=market_price_24h_ago,
        article_impacts=(ArticleImpact(direction="YES", source_weight=0.8),),
        t0=datetime(2026, 4, 25, tzinfo=timezone.utc),
    )


def test_market_price_abstains_when_price_is_exactly_half():
    """At price=0.5 the market has no directional signal — abstain."""
    p = baseline_market_price(_ctx(market_price=0.5))
    assert p.direction is None, (
        f"market_price emitted fake direction={p.direction!r} at price=0.5"
    )
    assert p.probability is None


def test_market_price_emits_buy_yes_when_above_half():
    p = baseline_market_price(_ctx(market_price=0.55))
    assert p.direction == "BUY_YES"
    assert p.probability == 0.55


def test_market_price_emits_buy_no_when_below_half():
    p = baseline_market_price(_ctx(market_price=0.45))
    assert p.direction == "BUY_NO"
    assert p.probability == 0.45


def test_momentum_abstains_when_return_is_exactly_zero():
    """When 24h price is unchanged the baseline has no signal — abstain."""
    p = baseline_momentum(_ctx(market_price=0.6, market_price_24h_ago=0.6))
    assert p.direction is None, (
        f"momentum emitted fake direction={p.direction!r} on flat 24h price"
    )
    assert p.probability is None


def test_momentum_emits_buy_yes_when_price_climbed():
    p = baseline_momentum(_ctx(market_price=0.7, market_price_24h_ago=0.5))
    assert p.direction == "BUY_YES"
    assert p.probability is not None and p.probability > 0.5


def test_momentum_emits_buy_no_when_price_fell():
    p = baseline_momentum(_ctx(market_price=0.3, market_price_24h_ago=0.5))
    assert p.direction == "BUY_NO"
    assert p.probability is not None and p.probability < 0.5
