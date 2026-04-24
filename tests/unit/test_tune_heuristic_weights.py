"""Chantier #5 — coordinate descent convergence + gate logic.

Tests run on synthetic data (no DB) so they are fast and deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass

from scripts.tune_heuristic_weights import (
    CandidateResult,
    coordinate_descent,
    evaluate_candidate,
    evaluation_gate,
)


@dataclass(frozen=True)
class _Sample:
    features: dict
    llm_combined: float
    direction: str
    price_t1h: float


def _make_synthetic_dataset() -> list[_Sample]:
    samples = []
    for f_val in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0] * 20:
        # outcome = 1 iff freshness > 0.5
        price = 0.98 if f_val > 0.5 else 0.02
        samples.append(_Sample(
            features={"freshness": f_val, "source_weight": 0.5, "confirmation": 0.5,
                      "liquidity": 0.5, "spread": 0.5, "time_to_resolution": 0.5},
            llm_combined=0.5,
            direction="BUY_YES" if f_val > 0.5 else "BUY_NO",
            price_t1h=price,
        ))
    return samples


def test_evaluate_candidate_returns_brier_and_pnl():
    samples = _make_synthetic_dataset()
    from app.scoring.weights import HeuristicWeights
    result = evaluate_candidate(HeuristicWeights.frozen_v1(), samples)
    assert isinstance(result, CandidateResult)
    assert 0.0 <= result.brier_mean <= 1.0
    assert result.n > 0


def test_coordinate_descent_moves_toward_better_config():
    """On synthetic data where freshness is the only signal, descent should
    push w_freshness above the 0.15 default, and the best Brier should be
    strictly below v1's baseline."""
    samples = _make_synthetic_dataset()
    best = coordinate_descent(samples, passes=2)
    assert best.weights.w_freshness > 0.15, (
        f"descent left w_freshness at {best.weights.w_freshness}"
    )
    from app.scoring.weights import HeuristicWeights
    baseline = evaluate_candidate(HeuristicWeights.frozen_v1(), samples)
    assert best.brier_mean < baseline.brier_mean


def test_coordinate_descent_idempotent_on_same_inputs():
    samples = _make_synthetic_dataset()
    a = coordinate_descent(samples, passes=2)
    b = coordinate_descent(samples, passes=2)
    assert a.weights == b.weights
    assert a.brier_mean == b.brier_mean
