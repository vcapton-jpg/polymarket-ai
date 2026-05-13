"""Audit 2026-04-25 follow-up [P0]: legitimate zero values must reach
the SignalBuilder, not get coerced to None by `if x else None`.

Background: `_run_full_scoring_pipeline` historically built `market_data`
and `llm_data` with `float(market.X) if market.X else None`. For 4706
active prod markets `last_trade_price == 0` exactly (deeply-NO markets);
for any market with a literal zero spread/liquidity/ambiguity_score the
same coercion flips a real measurement to None — bypassing downstream
filters and band checks. The fix is mechanical: switch to `is not None`.

This test pins the helpers that build the two dicts so the bug cannot
regress silently.
"""

from __future__ import annotations

from types import SimpleNamespace


def test_build_market_data_keeps_zero_price_and_spread_and_liquidity():
    from app.workers.tasks_scoring import _build_market_data

    m = SimpleNamespace(
        liquidity=0.0, spread=0.0, end_date=None, last_trade_price=0.0,
    )
    out = _build_market_data(m)
    assert out["liquidity"] == 0.0, "zero liquidity coerced to None"
    assert out["spread"] == 0.0, "zero spread coerced to None"
    assert out["last_trade_price"] == 0.0, "zero last_trade_price coerced to None"


def test_build_market_data_returns_none_for_actually_missing_values():
    from app.workers.tasks_scoring import _build_market_data

    # T-DATA added `best_bid` + `best_ask` (used to derive
    # `signal.spread_at_signal`). Keep this exhaustive equality check
    # so any future column addition forces a deliberate test update.
    m = SimpleNamespace(
        liquidity=None, spread=None, end_date=None,
        last_trade_price=None, category=None,
        best_bid=None, best_ask=None,
    )
    out = _build_market_data(m)
    assert out == {
        "liquidity": None, "spread": None,
        "end_date": None, "last_trade_price": None,
        "category": None,
        "best_bid": None, "best_ask": None,
    }


def test_build_market_data_passes_normal_values_through():
    from app.workers.tasks_scoring import _build_market_data

    m = SimpleNamespace(
        liquidity=12000.0, spread=0.05, end_date="2026-12-31",
        last_trade_price=0.42,
    )
    out = _build_market_data(m)
    assert out["liquidity"] == 12000.0
    assert out["spread"] == 0.05
    assert out["last_trade_price"] == 0.42
    assert out["end_date"] == "2026-12-31"


def test_build_llm_data_keeps_zero_scores():
    from app.workers.tasks_scoring import _build_llm_data

    a = SimpleNamespace(
        impact_direction="YES", impact_strength=0.0,
        llm_confidence=0.0, ambiguity_score=0.0, specificity_score=0.0,
    )
    out = _build_llm_data(a)
    assert out["impact_strength"] == 0.0
    assert out["llm_confidence"] == 0.0
    assert out["ambiguity_score"] == 0.0
    assert out["specificity_score"] == 0.0


def test_build_llm_data_returns_none_when_no_analysis():
    from app.workers.tasks_scoring import _build_llm_data

    assert _build_llm_data(None) is None


def test_build_llm_data_returns_none_for_actually_missing_scores():
    from app.workers.tasks_scoring import _build_llm_data

    a = SimpleNamespace(
        impact_direction="YES", impact_strength=None,
        llm_confidence=None, ambiguity_score=None, specificity_score=None,
    )
    out = _build_llm_data(a)
    assert out["impact_direction"] == "YES"
    assert out["impact_strength"] is None
    assert out["llm_confidence"] is None
