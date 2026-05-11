"""Pure function: compute trade quality from liquidity / spread / TTR features.

Mirrors the legacy `HeuristicScorer.compute_score` trade-bloc formula.
"""
from __future__ import annotations

from app.scoring.weights import HeuristicWeights

_NEUTRAL = 0.5


def compute_trade_quality(
    features: dict,
    weights: HeuristicWeights,
) -> float:
    """Weighted sum of liquidity + spread + time_to_resolution.

    Weights sum to 1.0 (HeuristicWeights invariant), so output ∈ [0,1] as
    long as each feature is in [0,1]. A defensive clamp guards against
    out-of-range inputs from legacy callers.
    """
    raw = (
        features.get("liquidity", _NEUTRAL) * weights.w_liquidity
        + features.get("spread", _NEUTRAL) * weights.w_spread
        + features.get("time_to_resolution", _NEUTRAL) * weights.w_time_to_resolution
    )
    return max(0.0, min(1.0, raw))
