"""Heuristic variant prediction builder.

`record_baselines` (pipeline.py) calls `predict_heuristic` once to build the
`heuristic_v1` row and, if the shadow flag is on, a second time with the
live Settings weights to build the `heuristic_shadow` row.

We duplicate the HeuristicScorer formula here rather than calling
`HeuristicScorer().compute_score()` for two reasons:
  - We need a VariantPrediction, not a dict; building one from the scorer
    output would require re-parsing the 0-100 int back to a probability.
  - The shadow path needs weights ≠ the live scorer's weights, so we can't
    reuse `HeuristicScorer()` without constructing a second one per signal.
"""
from __future__ import annotations

from app.measurement.variant_registry import VariantPrediction
from app.scoring.strength_scorer import compute_signal_strength
from app.scoring.trade_scorer import compute_trade_quality
from app.scoring.weights import HeuristicWeights


def predict_heuristic(
    *,
    weights: HeuristicWeights,
    features: dict,
    llm_combined: float | None,
    direction: str | None,
) -> VariantPrediction:
    """Compute a VariantPrediction under arbitrary heuristic weights.

    The probability maps the final [0,1] score directly to P(move in `direction`),
    usable as input to `brier_from_outcome` against a binarised short-horizon
    price and to `simulated_pnl_eur` against the raw price.
    """
    strength = compute_signal_strength(features, weights, llm_combined)
    trade = compute_trade_quality(features, weights)
    final = weights.strength_weight * strength + weights.trade_weight * trade
    return VariantPrediction(
        direction=direction,
        probability=max(0.0, min(1.0, final)),
    )
