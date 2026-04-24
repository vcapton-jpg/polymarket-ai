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


# ── Gate tests ──────────────────────────────────────────────────────
from app.scoring.weights import HeuristicWeights


def _mk_result(brier: float, pnl: float = 0.0, n: int = 2000) -> CandidateResult:
    # n=2000 so CIs are narrow enough that a 0.10 brier_mean gap
    # (e.g. 0.15 vs 0.25) separates disjointly at 95%.
    return CandidateResult(
        weights=HeuristicWeights.frozen_v1(),
        brier_mean=brier, pnl_mean=pnl, n=n, n_brier_defined=n,
    )


def test_gate_passes_when_candidate_is_cleanly_better():
    cand = _mk_result(brier=0.15, pnl=1.2)
    base = _mk_result(brier=0.25, pnl=1.0)
    g = evaluation_gate(candidate=cand, baseline_v1=base)
    assert g["passed"] is True
    assert g["brier_disjoint"] is True
    assert g["pnl_ok"] is True


def test_gate_rejects_when_brier_ci_overlaps():
    cand = _mk_result(brier=0.24, pnl=1.2)
    base = _mk_result(brier=0.25, pnl=1.0)
    g = evaluation_gate(candidate=cand, baseline_v1=base)
    assert g["passed"] is False
    assert g["brier_disjoint"] is False


def test_gate_rejects_when_pnl_regresses_past_tolerance():
    cand = _mk_result(brier=0.10, pnl=0.50)   # 50% P&L slip
    base = _mk_result(brier=0.25, pnl=1.00)
    g = evaluation_gate(candidate=cand, baseline_v1=base)
    assert g["passed"] is False
    assert g["pnl_ok"] is False
    # default tolerance 5% → pnl_floor = 0.95; 0.50 < 0.95 → fail
    assert g["pnl_floor"] == 0.95


def test_gate_rejects_when_bucket_regresses_past_cap():
    cand = _mk_result(brier=0.15, pnl=1.2)
    base = _mk_result(brier=0.25, pnl=1.0)
    buckets = {
        "high":   (_mk_result(brier=0.10, pnl=1.0), _mk_result(brier=0.15, pnl=0.9)),
        "medium": (_mk_result(brier=0.30, pnl=0.5), _mk_result(brier=0.20, pnl=0.8)),
    }
    g = evaluation_gate(candidate=cand, baseline_v1=base, per_bucket=buckets)
    assert g["passed"] is False
    assert g["bucket_ok"] is False
    assert g["buckets"]["medium"]["passed"] is False
    assert g["buckets"]["high"]["passed"] is True


def test_gate_passes_when_all_buckets_stable():
    cand = _mk_result(brier=0.15, pnl=1.2)
    base = _mk_result(brier=0.25, pnl=1.0)
    buckets = {
        "high":   (_mk_result(brier=0.10), _mk_result(brier=0.12)),
        "medium": (_mk_result(brier=0.16), _mk_result(brier=0.18)),
        "low":    (_mk_result(brier=0.22), _mk_result(brier=0.20)),  # +0.02 ≤ 0.05 OK
    }
    g = evaluation_gate(candidate=cand, baseline_v1=base, per_bucket=buckets)
    assert g["passed"] is True


def test_coordinate_descent_result_weights_sum_invariant_holds():
    """Every weights object the tuner can return must satisfy the
    HeuristicWeights sum-to-1 invariants."""
    samples = _make_synthetic_dataset()
    best = coordinate_descent(samples, passes=2)
    HeuristicWeights(**best.weights.__dict__)
