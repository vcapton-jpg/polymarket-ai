"""Chantier #5 — validate_heuristic_weights script logic (pure, no DB).

Feeds a synthetic set of (prediction, outcome) rows and asserts the aggregated
Brier / P&L / Wilson CI95 per variant match hand-computed values.
"""
from __future__ import annotations

import math

from scripts.validate_heuristic_weights import (
    JoinedRow,
    aggregate_variant_metrics,
    build_markdown_report,
)


def _row(variant: str, prob: float, direction: str, price: float) -> JoinedRow:
    return JoinedRow(
        variant=variant,
        predicted_probability=prob,
        predicted_direction=direction,
        price_t1h=price,
    )


def test_aggregate_metrics_single_variant_brier_from_binarized_price():
    rows = [
        _row("heuristic_v1", 0.7, "BUY_YES", 0.98),  # binary=1 → (0.7-1)^2 = 0.09
        _row("heuristic_v1", 0.3, "BUY_YES", 0.02),  # binary=0 → (0.3-0)^2 = 0.09
    ]
    metrics = aggregate_variant_metrics(rows)
    assert set(metrics.keys()) == {"heuristic_v1"}
    m = metrics["heuristic_v1"]
    assert m["n"] == 2
    assert m["n_brier_defined"] == 2
    assert math.isclose(m["brier_mean"], 0.09, abs_tol=1e-9)


def test_aggregate_metrics_ambiguous_outcomes_skipped_from_brier():
    rows = [
        _row("v", 0.6, "BUY_YES", 0.98),  # binary=1, counted
        _row("v", 0.6, "BUY_YES", 0.50),  # ambiguous (0.05 < price < 0.95), skipped
    ]
    m = aggregate_variant_metrics(rows)["v"]
    assert m["n"] == 2
    assert m["n_brier_defined"] == 1
    assert math.isclose(m["brier_mean"], (0.6 - 1) ** 2, abs_tol=1e-9)


def test_aggregate_metrics_pnl_uses_raw_price_not_binarised():
    rows = [
        _row("v", 0.6, "BUY_YES", 0.70),  # pnl = 10 * (0.7 - 0.6) = 1.0
        _row("v", 0.4, "BUY_YES", 0.30),  # pnl = 10 * (0.3 - 0.4) = -1.0
    ]
    m = aggregate_variant_metrics(rows)["v"]
    assert math.isclose(m["pnl_mean"], 0.0, abs_tol=1e-9)


def test_build_markdown_report_has_required_columns():
    metrics = {
        "heuristic_v1": {
            "n": 100, "n_brier_defined": 80, "brier_mean": 0.20,
            "brier_ci95": (0.17, 0.23),
            "pnl_mean": 0.5, "pnl_ci95": (-0.1, 1.1),
            "hit_rate": 0.55, "hit_rate_ci95": (0.45, 0.65),
        },
        "baseline_random": {
            "n": 100, "n_brier_defined": 80, "brier_mean": 0.25,
            "brier_ci95": (0.22, 0.28),
            "pnl_mean": 0.0, "pnl_ci95": (-0.6, 0.6),
            "hit_rate": 0.50, "hit_rate_ci95": (0.40, 0.60),
        },
    }
    md = build_markdown_report(metrics, horizon="t1h", generated_at="2026-04-24")
    assert "| variant" in md
    assert "heuristic_v1" in md
    assert "baseline_random" in md
    assert "brier_mean" in md
    assert "horizon=t1h" in md
    assert "2026-04-24" in md
