"""Tests for the coordinate-descent tuner."""
from __future__ import annotations

import pytest


def test_coordinate_descent_finds_global_optimum_on_unimodal_synth():
    from scripts.tune_event_market_ranking import coordinate_descent

    def score(cfg: dict) -> float:
        # Unimodal bowl: optimum at (w_entity=0.5, w_date=0.5).
        return -((cfg["w_entity"] - 0.5) ** 2 + (cfg["w_date"] - 0.5) ** 2)

    grid = {
        "w_entity": [0.1, 0.3, 0.5, 0.8, 1.2],
        "w_date":   [0.0, 0.2, 0.5, 1.0],
    }
    start = {"w_entity": 0.1, "w_date": 0.0}
    best = coordinate_descent(score, grid, start, passes=2)
    assert best["w_entity"] == 0.5
    assert best["w_date"] == 0.5


def test_coordinate_descent_idempotent_once_converged():
    from scripts.tune_event_market_ranking import coordinate_descent

    def score(cfg: dict) -> float:
        return -abs(cfg["x"] - 5)

    grid = {"x": [1, 3, 5, 7, 9]}
    best = coordinate_descent(score, grid, {"x": 1}, passes=3)
    assert best["x"] == 5


def test_coordinate_descent_respects_order_for_ties(monkeypatch):
    """When multiple values tie, keep the first in range order (deterministic)."""
    from scripts.tune_event_market_ranking import coordinate_descent
    grid = {"x": [1, 2, 3]}
    best = coordinate_descent(lambda cfg: 0.0, grid, {"x": 1}, passes=1)
    assert best["x"] == 1


def test_offline_gate_rejects_regression_on_any_bucket():
    from scripts.tune_event_market_ranking import evaluate_offline_gate
    v1 = {
        "overall": {"retrieval@5": {"mean": 0.40, "ci_low": 0.35, "ci_high": 0.45}},
        "per_bucket": {"politics": {"retrieval@5": {"mean": 0.50}}},
    }
    # v2 improves overall but politics regresses > 5%.
    v2 = {
        "overall": {"retrieval@5": {"mean": 0.55, "ci_low": 0.50, "ci_high": 0.60}},
        "per_bucket": {"politics": {"retrieval@5": {"mean": 0.40}}},
    }
    out = evaluate_offline_gate(v1, v2, max_bucket_regression=0.05)
    assert out["status"] == "failed"
    assert "politics" in out["reason"]


def test_offline_gate_accepts_strict_ci_improvement():
    from scripts.tune_event_market_ranking import evaluate_offline_gate
    v1 = {
        "overall": {
            "retrieval@5": {"mean": 0.40, "ci_low": 0.35, "ci_high": 0.45},
            "ndcg@10":     {"mean": 0.50},
        },
        "per_bucket": {"politics": {"retrieval@5": {"mean": 0.40}}},
    }
    v2 = {
        "overall": {
            "retrieval@5": {"mean": 0.55, "ci_low": 0.50, "ci_high": 0.60},
            "ndcg@10":     {"mean": 0.55},
        },
        "per_bucket": {"politics": {"retrieval@5": {"mean": 0.42}}},
    }
    out = evaluate_offline_gate(v1, v2, max_bucket_regression=0.05)
    assert out["status"] == "passed"
