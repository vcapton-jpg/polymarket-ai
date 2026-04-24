"""Unit tests for app.eval.metrics — pure functions, no I/O.

Covers every documented edge case in §4.2 of the spec."""

from __future__ import annotations

import math

import pytest

from app.eval.metrics import (
    aggregate,
    bootstrap_ci,
    cluster_purity,
    ndcg_at_k,
    retrieval_at_k,
)


# ── retrieval@k ──────────────────────────────────────────────────────
def test_retrieval_at_k_all_relevant_in_top_k():
    assert retrieval_at_k({1, 2}, [1, 2, 3, 4, 5], k=5) == pytest.approx(1.0)


def test_retrieval_at_k_partial_match():
    # 1 of 2 relevant items is in top-5.
    assert retrieval_at_k({1, 99}, [1, 2, 3, 4, 5], k=5) == pytest.approx(0.5)


def test_retrieval_at_k_none_in_top_k():
    assert retrieval_at_k({99}, [1, 2, 3, 4, 5], k=5) == pytest.approx(0.0)


def test_retrieval_at_k_k_larger_than_ranked():
    # Only 3 candidates, k=5 → normalize against min(k, |relevant|).
    assert retrieval_at_k({1}, [1, 2, 3], k=5) == pytest.approx(1.0)


def test_retrieval_at_k_empty_relevant_returns_zero():
    assert retrieval_at_k(set(), [1, 2, 3], k=5) == 0.0


def test_retrieval_at_k_empty_ranked_returns_zero():
    assert retrieval_at_k({1}, [], k=5) == 0.0


def test_retrieval_at_k_k_zero_returns_zero():
    assert retrieval_at_k({1}, [1, 2, 3], k=0) == 0.0


def test_retrieval_at_k_duplicates_in_ranked_do_not_double_count():
    # 1 appears twice in the ranked list; it's one relevant hit.
    assert retrieval_at_k({1}, [1, 1, 2, 3], k=4) == pytest.approx(1.0)


# ── nDCG@k ───────────────────────────────────────────────────────────
def test_ndcg_at_k_perfect_ranking_is_one():
    assert ndcg_at_k({1, 2}, [1, 2, 3, 4], k=4) == pytest.approx(1.0, abs=1e-9)


def test_ndcg_at_k_reversed_is_less_than_one():
    # Relevant at positions 3 and 4 — worse than perfect.
    v = ndcg_at_k({1, 2}, [3, 4, 1, 2], k=4)
    assert 0.0 < v < 1.0


def test_ndcg_at_k_no_relevant_in_ranked_returns_zero():
    assert ndcg_at_k({99}, [1, 2, 3], k=3) == 0.0


def test_ndcg_at_k_empty_relevant_returns_zero():
    assert ndcg_at_k(set(), [1, 2, 3], k=3) == 0.0


# ── bootstrap CI ─────────────────────────────────────────────────────
def test_bootstrap_ci_deterministic_with_seed():
    values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    a = bootstrap_ci(values, n_resamples=500, alpha=0.05, seed=42)
    b = bootstrap_ci(values, n_resamples=500, alpha=0.05, seed=42)
    assert a == b


def test_bootstrap_ci_mean_close_to_sample_mean():
    values = [0.5] * 20
    mean, ci_low, ci_high = bootstrap_ci(values, n_resamples=500, alpha=0.05, seed=42)
    assert mean == pytest.approx(0.5, abs=1e-6)
    assert ci_low == pytest.approx(0.5, abs=1e-6)
    assert ci_high == pytest.approx(0.5, abs=1e-6)


def test_bootstrap_ci_empty_values_returns_zero_triple():
    assert bootstrap_ci([], n_resamples=100, alpha=0.05, seed=42) == (0.0, 0.0, 0.0)


# ── aggregate ────────────────────────────────────────────────────────
def test_aggregate_mean_ci_and_n():
    per_pair = [
        {"retrieval@5": 0.8, "source": "db_heuristic"},
        {"retrieval@5": 0.6, "source": "db_heuristic"},
        {"retrieval@5": 1.0, "source": "llm_judge"},
    ]
    out = aggregate(per_pair, strata=("source",))
    assert out["retrieval@5"]["n"] == 3
    assert out["retrieval@5"]["mean"] == pytest.approx(0.8, abs=1e-6)
    assert "per_source" in out
    assert out["per_source"]["db_heuristic"]["retrieval@5"]["n"] == 2
    assert out["per_source"]["llm_judge"]["retrieval@5"]["n"] == 1


def test_aggregate_empty_per_pair_returns_empty_summary():
    out = aggregate([], strata=("source",))
    assert out == {"per_source": {}}


# ── cluster_purity ───────────────────────────────────────────────────
def test_cluster_purity_perfect_clustering_is_one():
    clusters = {1: [10, 11, 12], 2: [20, 21]}
    truth = {10: 1, 11: 1, 12: 1, 20: 2, 21: 2}
    assert cluster_purity(clusters, truth) == pytest.approx(1.0)


def test_cluster_purity_majority_rule():
    # Cluster 1 has 2 label-A and 1 label-B → purity contribution = 2/3.
    # Cluster 2 is 2 label-B → purity contribution = 2/2.
    # Overall = (2 + 2) / (3 + 2) = 4/5.
    clusters = {1: [10, 11, 20], 2: [21, 22]}
    truth = {10: 1, 11: 1, 20: 2, 21: 2, 22: 2}
    assert cluster_purity(clusters, truth) == pytest.approx(0.8, abs=1e-6)


def test_cluster_purity_ignores_items_without_truth():
    clusters = {1: [10, 11, 99]}   # 99 has no ground-truth label
    truth = {10: 1, 11: 1}
    # 99 is excluded from both numerator and denominator.
    assert cluster_purity(clusters, truth) == pytest.approx(1.0)
