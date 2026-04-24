"""Chantier #5 — predict_heuristic helper.

Used by record_baselines to produce a VariantPrediction for both the frozen
heuristic_v1 (reference) and the configurable heuristic_shadow (experimental)
without touching the production scoring path.
"""
from __future__ import annotations

import pytest

from app.measurement.heuristic_variant import predict_heuristic
from app.measurement.variant_registry import VariantPrediction
from app.scoring.weights import HeuristicWeights


def _sample_features(**overrides) -> dict:
    base = {
        "freshness": 0.6, "source_weight": 0.5, "confirmation": 0.7,
        "liquidity": 0.8, "spread": 0.4, "time_to_resolution": 0.5,
    }
    base.update(overrides)
    return base


def test_returns_variant_prediction_with_direction_and_probability():
    pred = predict_heuristic(
        weights=HeuristicWeights.frozen_v1(),
        features=_sample_features(),
        llm_combined=0.7,
        direction="BUY_YES",
    )
    assert isinstance(pred, VariantPrediction)
    assert pred.direction == "BUY_YES"
    assert pred.probability is not None
    assert 0.0 <= pred.probability <= 1.0


def test_probability_matches_hand_computed_value():
    """Pins: probability = strength_weight * strength + trade_weight * trade."""
    weights = HeuristicWeights.frozen_v1()
    features = {
        "freshness": 0.8, "source_weight": 0.6, "confirmation": 0.7,
        "liquidity": 0.9, "spread": 0.4, "time_to_resolution": 0.5,
    }
    # strength_base = 0.8*0.15 + 0.6*0.10 + 0.7*0.15 = 0.285
    # strength_raw  = 0.285 + 0.75*0.60 = 0.735
    # trade_raw     = 0.9*0.40 + 0.4*0.35 + 0.5*0.25 = 0.625
    # final         = 0.75*0.735 + 0.25*0.625 = 0.7075
    pred = predict_heuristic(
        weights=weights, features=features, llm_combined=0.75, direction="BUY_YES",
    )
    assert abs(pred.probability - 0.7075) < 1e-6


def test_heuristic_v1_differs_from_shadow_when_weights_differ():
    """Different weights → different probability for the same features."""
    features = _sample_features()
    v1 = predict_heuristic(
        weights=HeuristicWeights.frozen_v1(),
        features=features, llm_combined=0.8, direction="BUY_YES",
    )
    shadow = predict_heuristic(
        weights=HeuristicWeights(
            w_freshness=0.40, w_source=0.10, w_confirmation=0.10, w_llm=0.40,
            w_liquidity=0.40, w_spread=0.35, w_time_to_resolution=0.25,
            strength_weight=0.50, trade_weight=0.50,
        ),
        features=features, llm_combined=0.8, direction="BUY_YES",
    )
    assert v1.probability != pytest.approx(shadow.probability)


def test_probability_clamped_to_unit_interval():
    """Out-of-range features still produce a probability in [0,1]."""
    features = {
        "freshness": 2.0, "source_weight": 2.0, "confirmation": 2.0,
        "liquidity": 2.0, "spread": 2.0, "time_to_resolution": 2.0,
    }
    pred = predict_heuristic(
        weights=HeuristicWeights.frozen_v1(),
        features=features, llm_combined=2.0, direction="BUY_YES",
    )
    assert 0.0 <= pred.probability <= 1.0


def test_direction_passed_through_unchanged():
    for d in ("BUY_YES", "BUY_NO", None):
        pred = predict_heuristic(
            weights=HeuristicWeights.frozen_v1(),
            features=_sample_features(), llm_combined=0.5, direction=d,
        )
        assert pred.direction == d
