"""P1.1 (audit 2026-04-25): `baseline_news_sentiment` must ABSTAIN when
the cluster carries no directional information, NOT invent a fake
BUY_NO @ 0.5 prediction.

Background: in production, `_fetch_baseline_articles` returns articles
with `source_weight` only — no `direction_hint`. `build_scoring_context`
defaults missing directions to "NEUTRAL", so every article in every
cluster gets sentiment 0. The current implementation then takes the
`sentiment > 0` branch (false), assigns "BUY_NO", and emits
probability = sigmoid(0) = 0.5. Result: 311+ prod
`baseline_news_sentiment` rows are fake BUY_NO @ 0.5 — they don't reflect
news content at all and pollute every cross-baseline Brier comparison.

Fix: when total weighted sentiment is exactly 0 (all NEUTRAL or balanced
mix), abstain — return (None, None) like other baselines do when they
lack data. The variant row is still written; it just carries no
prediction. That keeps the registry honest until per-article direction
is wired upstream.
"""

from __future__ import annotations

import pytest

from app.measurement.baselines import baseline_news_sentiment
from app.measurement.scoring_context import ArticleImpact, ScoringContext


def _ctx(articles):
    from datetime import datetime, timezone
    return ScoringContext(
        signal_id=1, market_id="m", event_id=1,
        market_price=0.5, market_price_24h_ago=None,
        article_impacts=tuple(articles),
        t0=datetime(2026, 4, 25, tzinfo=timezone.utc),
    )


def test_all_neutral_articles_abstain_with_none():
    """All-NEUTRAL articles must yield (None, None), not (BUY_NO, 0.5)."""
    arts = (
        ArticleImpact(direction="NEUTRAL", source_weight=0.9),
        ArticleImpact(direction="NEUTRAL", source_weight=0.7),
    )
    p = baseline_news_sentiment(_ctx(arts))
    assert p.direction is None, (
        f"all-NEUTRAL must abstain, got direction={p.direction!r} — that's "
        "the P1.1 bug producing 311+ fake BUY_NO @ 0.5 prod rows."
    )
    assert p.probability is None, (
        f"all-NEUTRAL must abstain, got probability={p.probability!r}."
    )


def test_balanced_yes_no_abstains_with_none():
    """A perfectly balanced YES/NO mix (sentiment == 0) must also abstain."""
    arts = (
        ArticleImpact(direction="YES", source_weight=0.5),
        ArticleImpact(direction="NO", source_weight=0.5),
    )
    p = baseline_news_sentiment(_ctx(arts))
    assert p.direction is None
    assert p.probability is None
