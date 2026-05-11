"""Pure function: compute signal strength from features + weights + LLM signal.

Bit-exactly reproduces the formula previously embedded in
`HeuristicScorer.compute_score` so the refactor is semantics-preserving.

Shape: features ∈ [0,1] per key, weights sum to 1.0 (enforced by
HeuristicWeights), output ∈ [0,1].
"""
from __future__ import annotations

from app.scoring.weights import HeuristicWeights

_NEUTRAL = 0.5  # legacy fallback when a feature key is missing


def compute_signal_strength(
    features: dict,
    weights: HeuristicWeights,
    llm_combined: float | None,
) -> float:
    """Weighted combination of backend features + LLM signal.

    When `llm_combined` is not None:
        score = Σ(w_k * features[k]) + w_llm * llm_combined

    When `llm_combined` is None (LLM unavailable):
        score = Σ(w_k * features[k]) / (1 - w_llm)

    That second branch renormalises the backend bloc to the full [0,1] range,
    so a signal with no LLM isn't artificially penalised to 40% of max.
    Preserved from the legacy HeuristicScorer semantics.
    """
    backend_sum = (
        features.get("freshness", _NEUTRAL) * weights.w_freshness
        + features.get("source_weight", _NEUTRAL) * weights.w_source
        + features.get("confirmation", _NEUTRAL) * weights.w_confirmation
    )
    if llm_combined is None:
        # Renormalise. If w_llm == 1.0 we'd divide by zero — treat that as
        # "backend has no signal, fall back to neutral 0.5".
        remaining = 1.0 - weights.w_llm
        if remaining < 1e-9:
            return _NEUTRAL
        return max(0.0, min(1.0, backend_sum / remaining))
    raw = backend_sum + llm_combined * weights.w_llm
    return max(0.0, min(1.0, raw))
