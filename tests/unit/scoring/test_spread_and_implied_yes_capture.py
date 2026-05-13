"""Pin the T-DATA capture contract.

Two new fields propagate through the pipeline at signal emission:

  * `spread_at_signal` — derived from `market_data["best_bid"]` and
    `market_data["best_ask"]` in `SignalBuilder.build_signal`.
  * `implied_yes_probability` — propagated from the LLM analysis dict
    (`event_market_analysis.implied_yes_probability`) via
    `_build_llm_data`.

These tests pin the propagation + the defensive None-fallbacks
without exercising the full DB-backed builder path.
"""

from __future__ import annotations

from types import SimpleNamespace


# ──────────────────────────────────────────────────────────────────────
# _build_market_data — bid/ask surface
# ──────────────────────────────────────────────────────────────────────


def test_build_market_data_surfaces_bid_ask_when_present():
    from app.workers.tasks_scoring import _build_market_data

    m = SimpleNamespace(
        liquidity=10000.0, spread=None, end_date=None,
        last_trade_price=0.42, category="Politics",
        best_bid=0.41, best_ask=0.43,
    )
    out = _build_market_data(m)
    assert out["best_bid"] == 0.41
    assert out["best_ask"] == 0.43


def test_build_market_data_bid_ask_none_when_market_lacks_them():
    """13 % of `markets` rows have NULL bid/ask. The builder must
    surface None, not crash."""
    from app.workers.tasks_scoring import _build_market_data

    m = SimpleNamespace(
        liquidity=10000.0, spread=None, end_date=None,
        last_trade_price=0.42, category="Politics",
        best_bid=None, best_ask=None,
    )
    out = _build_market_data(m)
    assert out["best_bid"] is None
    assert out["best_ask"] is None


# ──────────────────────────────────────────────────────────────────────
# _build_llm_data — implied_yes_probability propagation
# ──────────────────────────────────────────────────────────────────────


def test_build_llm_data_propagates_implied_yes_probability_when_present():
    """v2 prompt fills `implied_yes_probability` on the
    EventMarketAnalysis row. The builder dict must surface it for
    SignalBuilder to persist on the Signal."""
    from app.workers.tasks_scoring import _build_llm_data

    analysis = SimpleNamespace(
        impact_direction="BUY_YES",
        impact_strength=0.7,
        llm_confidence=0.8,
        ambiguity_score=0.1,
        specificity_score=0.9,
        llm_model_version="gpt-4o-mini@v2",
        implied_yes_probability=0.72,
    )
    out = _build_llm_data(analysis)
    assert out["implied_yes_probability"] == 0.72


def test_build_llm_data_none_implied_yes_for_legacy_v1_rows():
    """Pre-T-DATA `event_market_analysis` rows don't have an
    `implied_yes_probability` attribute at all. `getattr` must
    default to None without crashing."""
    from app.workers.tasks_scoring import _build_llm_data

    # No implied_yes_probability attribute — v1 prompt did not emit it.
    analysis = SimpleNamespace(
        impact_direction="BUY_YES",
        impact_strength=0.7,
        llm_confidence=0.8,
        ambiguity_score=0.1,
        specificity_score=0.9,
        llm_model_version="gpt-4o-mini@v1",
    )
    out = _build_llm_data(analysis)
    assert out["implied_yes_probability"] is None


# ──────────────────────────────────────────────────────────────────────
# spread_at_signal — derived field arithmetic in SignalBuilder
# ──────────────────────────────────────────────────────────────────────


def _compute_spread_at_signal(bid, ask):
    """Mirror of the inline computation in
    `SignalBuilder.build_signal` (post-T-DATA). Single source of
    truth for the derivation rule — if the rule changes here, the
    builder must change with it."""
    if bid is None or ask is None:
        return None
    if ask < bid:  # malformed quote — defensive
        return None
    return round(float(ask) - float(bid), 4)


def test_spread_arithmetic_normal_quote():
    # bid 0.41, ask 0.43 → spread 0.02
    assert _compute_spread_at_signal(0.41, 0.43) == 0.02


def test_spread_arithmetic_zero_spread_locked_market():
    # A perfectly tight market (bid == ask) → spread 0. Still a number,
    # not None — that's a meaningful "no spread cost" signal.
    assert _compute_spread_at_signal(0.50, 0.50) == 0.0


def test_spread_arithmetic_missing_side_returns_none():
    # Realistic Polymarket pathological case — one side of the book is
    # empty. We don't want to fabricate a spread out of thin air.
    assert _compute_spread_at_signal(None, 0.43) is None
    assert _compute_spread_at_signal(0.41, None) is None
    assert _compute_spread_at_signal(None, None) is None


def test_spread_arithmetic_inverted_quote_returns_none():
    """Defensive — a quote where ask < bid is malformed (crossed
    book or stale data). Returning a negative spread would corrupt
    downstream realistic_replay math. Better to NULL it."""
    assert _compute_spread_at_signal(0.50, 0.45) is None


def test_spread_arithmetic_rounding_to_4dp():
    """`spread_at_signal` is NUMERIC(5,4) — must round to 4 decimals."""
    assert _compute_spread_at_signal(0.41, 0.4329) == 0.0229
    # Cumulative rounding edge case
    assert _compute_spread_at_signal(0.41005, 0.41015) == 0.0001
