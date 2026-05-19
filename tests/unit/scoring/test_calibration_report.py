"""Pin the calibration-report pure stats (LEVIER-2 decision support).

Ground-truth-free tests on the closed-form math: Brier, optimal
shrink s*, and reliability bucketing. These are the numbers the
H+72 levier-2 decision will be made on, so they must be exact.
"""

from __future__ import annotations

import pytest

from scripts.shadow.calibration_report import (
    brier,
    optimal_shrink,
    reliability_buckets,
)


# ── Brier ─────────────────────────────────────────────────────────────


def test_brier_perfect_predictions_is_zero():
    assert brier([(0.0, 0.0), (1.0, 1.0), (0.5, 0.5)]) == 0.0


def test_brier_known_value():
    # (0.8-0.6)^2 + (0.2-0.5)^2 = 0.04 + 0.09 = 0.13 ; /2 = 0.065
    assert brier([(0.8, 0.6), (0.2, 0.5)]) == pytest.approx(0.065)


def test_brier_empty_is_none():
    assert brier([]) is None


# ── optimal_shrink ────────────────────────────────────────────────────


def test_optimal_shrink_identity_when_already_calibrated():
    # actual == predicted everywhere → s* must be exactly 1.0
    pairs = [(0.2, 0.2), (0.8, 0.8), (0.35, 0.35), (0.9, 0.9)]
    assert optimal_shrink(pairs) == pytest.approx(1.0)


def test_optimal_shrink_detects_over_confidence():
    # Model says 0.9/0.1 but reality is only 0.7/0.3 (compressed
    # toward 0.5). s* should be < 1 (shrink helps).
    pairs = [(0.9, 0.7), (0.1, 0.3), (0.9, 0.7), (0.1, 0.3)]
    s = optimal_shrink(pairs)
    # (p-0.5)=±0.4, (a-0.5)=±0.2 → s* = Σ0.4*0.2 / Σ0.4^2 = 0.08/0.16 = 0.5
    assert s == pytest.approx(0.5)


def test_optimal_shrink_detects_under_confidence():
    # Model timid (0.6/0.4) but reality extreme (0.9/0.1).
    # s* should be > 1 (shrinking would be wrong).
    pairs = [(0.6, 0.9), (0.4, 0.1)]
    s = optimal_shrink(pairs)
    # (p-0.5)=±0.1, (a-0.5)=±0.4 → s* = Σ0.1*0.4 / Σ0.1^2 = 0.08/0.02 = 4
    assert s == pytest.approx(4.0)
    assert s > 1.15  # the report would say "shrinking is WRONG"


def test_optimal_shrink_none_when_no_variance():
    # All predictions exactly 0.5 → denominator 0 → undefined.
    assert optimal_shrink([(0.5, 0.3), (0.5, 0.8)]) is None


def test_optimal_shrink_minimises_brier():
    # Cross-check the closed form against a brute-force grid: the s*
    # it returns must give a Brier no worse than any nearby s.
    pairs = [(0.85, 0.62), (0.15, 0.34), (0.70, 0.55), (0.30, 0.40), (0.92, 0.70)]
    s_star = optimal_shrink(pairs)
    assert s_star is not None

    def b(s):
        return brier([(0.5 + (p - 0.5) * s, a) for p, a in pairs])

    best = b(s_star)
    for delta in (-0.2, -0.1, -0.05, 0.05, 0.1, 0.2):
        assert b(s_star + delta) >= best - 1e-9


# ── reliability_buckets ───────────────────────────────────────────────


def test_reliability_buckets_groups_by_decile():
    pairs = [
        (0.05, 0.10),  # bucket 0.0-0.1
        (0.07, 0.20),  # bucket 0.0-0.1
        (0.55, 0.50),  # bucket 0.5-0.6
        (0.99, 0.70),  # bucket 0.9-1.0
    ]
    out = reliability_buckets(pairs, n_buckets=10)
    by = {r["bucket"]: r for r in out}
    assert by["0.0-0.1"]["n"] == 2
    assert by["0.0-0.1"]["pred_mean"] == pytest.approx(0.06)
    assert by["0.0-0.1"]["actual_mean"] == pytest.approx(0.15)
    assert by["0.0-0.1"]["gap"] == pytest.approx(-0.09)
    assert by["0.9-1.0"]["n"] == 1
    # Sparse buckets are omitted, not zero-filled.
    assert "0.2-0.3" not in by


def test_reliability_bucket_edge_1_0_lands_in_last_bucket():
    # p == 1.0 → int(1.0*10)=10 → must clamp to bucket index 9.
    out = reliability_buckets([(1.0, 0.9)], n_buckets=10)
    assert len(out) == 1
    assert out[0]["bucket"] == "0.9-1.0"
