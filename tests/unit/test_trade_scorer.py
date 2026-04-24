"""Chantier #5 — trade_scorer pure function.

Mirrors test_strength_scorer.py: monotone + zero-weight per weight,
output bounds, missing-key neutrality.
"""
from __future__ import annotations

from app.scoring.trade_scorer import compute_trade_quality
from app.scoring.weights import HeuristicWeights


def _neutral_features(**overrides):
    base = {
        "liquidity": 0.5,
        "spread": 0.5,
        "time_to_resolution": 0.5,
    }
    base.update(overrides)
    return base


# ---- liquidity ---------------------------------------------------------

def test_liquidity_monotone():
    w = HeuristicWeights()
    low = compute_trade_quality(_neutral_features(liquidity=0.0), w)
    high = compute_trade_quality(_neutral_features(liquidity=1.0), w)
    assert high > low


def test_liquidity_zero_weight_eliminates_effect():
    w = HeuristicWeights(
        w_liquidity=0.0, w_spread=0.60, w_time_to_resolution=0.40,
    )
    a = compute_trade_quality(_neutral_features(liquidity=0.0), w)
    b = compute_trade_quality(_neutral_features(liquidity=1.0), w)
    assert a == b


# ---- spread ------------------------------------------------------------

def test_spread_monotone():
    w = HeuristicWeights()
    low = compute_trade_quality(_neutral_features(spread=0.0), w)
    high = compute_trade_quality(_neutral_features(spread=1.0), w)
    assert high > low


def test_spread_zero_weight_eliminates_effect():
    w = HeuristicWeights(
        w_liquidity=0.60, w_spread=0.0, w_time_to_resolution=0.40,
    )
    a = compute_trade_quality(_neutral_features(spread=0.0), w)
    b = compute_trade_quality(_neutral_features(spread=1.0), w)
    assert a == b


# ---- time_to_resolution ------------------------------------------------

def test_time_to_resolution_monotone():
    w = HeuristicWeights()
    low = compute_trade_quality(_neutral_features(time_to_resolution=0.0), w)
    high = compute_trade_quality(_neutral_features(time_to_resolution=1.0), w)
    assert high > low


def test_time_to_resolution_zero_weight_eliminates_effect():
    w = HeuristicWeights(
        w_liquidity=0.60, w_spread=0.40, w_time_to_resolution=0.0,
    )
    a = compute_trade_quality(_neutral_features(time_to_resolution=0.0), w)
    b = compute_trade_quality(_neutral_features(time_to_resolution=1.0), w)
    assert a == b


# ---- bounds + neutrality -----------------------------------------------

def test_output_bounded_in_unit_interval():
    w = HeuristicWeights()
    for val in (0.0, 0.25, 0.5, 0.75, 1.0):
        score = compute_trade_quality(_neutral_features(
            liquidity=val, spread=val, time_to_resolution=val,
        ), w)
        assert 0.0 <= score <= 1.0


def test_missing_feature_defaults_to_neutral():
    w = HeuristicWeights()
    full = compute_trade_quality(
        {"liquidity": 0.5, "spread": 0.5, "time_to_resolution": 0.5}, w
    )
    partial = compute_trade_quality({}, w)
    assert abs(full - partial) < 1e-9
