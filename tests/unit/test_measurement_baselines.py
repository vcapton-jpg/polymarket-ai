from datetime import datetime, timezone

import pytest

from app.measurement.baselines import (
    baseline_market_price,
    baseline_momentum,
    baseline_news_sentiment,
    baseline_random,
)
from app.measurement.scoring_context import ArticleImpact, ScoringContext


def _ctx(signal_id: int = 1, price: float = 0.6,
         price_24h: float | None = None,
         articles: tuple[ArticleImpact, ...] = ()) -> ScoringContext:
    return ScoringContext(
        signal_id=signal_id,
        market_id="0xdeadbeef",
        event_id=1,
        market_price=price,
        market_price_24h_ago=price_24h,
        article_impacts=articles,
        t0=datetime(2026, 4, 23, tzinfo=timezone.utc),
    )


# -- random -----------------------------------------------------------
def test_baseline_random_deterministic_for_same_signal_id():
    a = baseline_random(_ctx(signal_id=42))
    b = baseline_random(_ctx(signal_id=42))
    assert a == b


def test_baseline_random_probability_always_half():
    for sid in [1, 7, 99, 12345]:
        assert baseline_random(_ctx(signal_id=sid)).probability == 0.5


def test_baseline_random_direction_varies_by_signal_id():
    directions = {baseline_random(_ctx(signal_id=i)).direction for i in range(50)}
    assert directions == {"BUY_YES", "BUY_NO"}


# -- market_price -----------------------------------------------------
@pytest.mark.parametrize("price,expected_dir", [
    (0.0, "BUY_NO"),
    (0.49, "BUY_NO"),
    (0.51, "BUY_YES"),
    (1.0, "BUY_YES"),
])
def test_baseline_market_price_direction(price, expected_dir):
    p = baseline_market_price(_ctx(price=price))
    assert p.direction == expected_dir
    assert p.probability == price


def test_baseline_market_price_abstains_at_exactly_half():
    """Audit follow-up [P1]: at price=0.5 the market has no directional
    signal — emit (None, None) instead of a fake BUY_NO @ 0.5."""
    p = baseline_market_price(_ctx(price=0.5))
    assert p.direction is None
    assert p.probability is None


# -- momentum ---------------------------------------------------------
def test_baseline_momentum_returns_none_when_history_missing():
    p = baseline_momentum(_ctx(price=0.7, price_24h=None))
    assert p.direction is None
    assert p.probability is None


def test_baseline_momentum_positive_return_buys_yes():
    p = baseline_momentum(_ctx(price=0.7, price_24h=0.5))
    assert p.direction == "BUY_YES"
    assert p.probability == pytest.approx(0.5 + 0.5 * 0.2, abs=1e-6)


def test_baseline_momentum_negative_return_buys_no():
    p = baseline_momentum(_ctx(price=0.3, price_24h=0.5))
    assert p.direction == "BUY_NO"
    assert p.probability == pytest.approx(0.5 + 0.5 * (-0.2), abs=1e-6)


def test_baseline_momentum_clips_extreme_return():
    p = baseline_momentum(_ctx(price=1.0, price_24h=0.0))
    # 0.5 + 0.5 * 1.0 = 1.0, clipped to 0.99
    assert p.probability == pytest.approx(0.99, abs=1e-6)


# -- news_sentiment ---------------------------------------------------
def test_baseline_news_sentiment_empty_articles_none():
    p = baseline_news_sentiment(_ctx(articles=()))
    assert p.direction is None and p.probability is None


def test_baseline_news_sentiment_weighted_majority_yes():
    arts = (
        ArticleImpact(direction="YES", source_weight=0.9),
        ArticleImpact(direction="NO", source_weight=0.2),
    )
    p = baseline_news_sentiment(_ctx(articles=arts))
    assert p.direction == "BUY_YES"
    assert p.probability is not None and p.probability > 0.5


def test_baseline_news_sentiment_neutral_articles_abstain():
    """All-NEUTRAL → no directional information → abstain (None, None).

    Pre-fix this returned (BUY_NO, 0.5) — see audit 2026-04-25 P1.1.
    """
    arts = (
        ArticleImpact(direction="NEUTRAL", source_weight=0.9),
        ArticleImpact(direction="NEUTRAL", source_weight=0.7),
    )
    p = baseline_news_sentiment(_ctx(articles=arts))
    assert p.direction is None
    assert p.probability is None


def test_baseline_news_sentiment_weighted_majority_no():
    arts = (
        ArticleImpact(direction="NO", source_weight=0.8),
        ArticleImpact(direction="YES", source_weight=0.1),
    )
    p = baseline_news_sentiment(_ctx(articles=arts))
    assert p.direction == "BUY_NO"
    assert p.probability is not None and p.probability < 0.5
