"""Config integrity tests — catches config ↔ code drift.

Audit chantier #1: the `clustering_cosine_threshold` divergence (0.75 in
settings default vs 0.82 hard-coded in `simple_clusterer.py`) meant the
doc and the runtime disagreed for months, and nobody knew which value had
actually been used on historical data. These tests pin every runtime
constant to its canonical settings default so the next drift fails CI.
"""
from __future__ import annotations

import pytest

from app.core.config import Settings


def test_simple_clusterer_defaults_match_settings():
    """Module-level defaults must equal the Settings field defaults."""
    from app.event_engine.simple_clusterer import (
        DEFAULT_COSINE_THRESHOLD,
        DEFAULT_TIME_WINDOW_MINUTES,
    )

    defaults = Settings.model_fields
    assert DEFAULT_COSINE_THRESHOLD == defaults["clustering_cosine_threshold"].default, (
        f"simple_clusterer.DEFAULT_COSINE_THRESHOLD={DEFAULT_COSINE_THRESHOLD} "
        f"diverges from Settings.clustering_cosine_threshold default="
        f"{defaults['clustering_cosine_threshold'].default}"
    )
    assert DEFAULT_TIME_WINDOW_MINUTES == defaults["clustering_time_window_minutes"].default, (
        f"simple_clusterer.DEFAULT_TIME_WINDOW_MINUTES={DEFAULT_TIME_WINDOW_MINUTES} "
        f"diverges from Settings.clustering_time_window_minutes default="
        f"{defaults['clustering_time_window_minutes'].default}"
    )


def test_create_simple_clusterer_uses_settings():
    """`create_simple_clusterer()` must read from Settings, not module defaults.

    This is the prod wiring — if someone accidentally switches the factory
    back to the hard-coded module default, this test fails.
    """
    from app.core.config import get_settings
    from app.event_engine.simple_clusterer import create_simple_clusterer

    clusterer = create_simple_clusterer()
    s = get_settings()
    assert clusterer.cosine_threshold == s.clustering_cosine_threshold
    assert clusterer.time_window_minutes == s.clustering_time_window_minutes


@pytest.mark.parametrize("attr,expected_type", [
    ("clustering_cosine_threshold", float),
    ("clustering_time_window_minutes", int),
    ("rrf_k", int),
    ("ranking_v2_rrf_k", int),
    ("ranking_v2_w_entity", float),
    ("ranking_v2_w_date", float),
    ("ranking_v2_w_bucket", float),
    ("ranking_v2_tau_days", float),
    ("ranking_v2_min_sim", float),
    # Chantier #5 — heuristic score knobs
    ("heuristic_shadow_enabled", bool),
    ("heuristic_w_freshness", float),
    ("heuristic_w_source", float),
    ("heuristic_w_confirmation", float),
    ("heuristic_w_llm", float),
    ("heuristic_w_liquidity", float),
    ("heuristic_w_spread", float),
    ("heuristic_w_time_to_resolution", float),
    ("heuristic_strength_weight", float),
    ("heuristic_trade_weight", float),
])
def test_settings_field_types(attr: str, expected_type: type):
    """Pin the declared type of settings fields we reason about elsewhere."""
    defaults = Settings.model_fields
    assert attr in defaults, f"Settings missing expected field {attr!r}"
    default = defaults[attr].default
    assert isinstance(default, expected_type), (
        f"Settings.{attr} default {default!r} has type {type(default).__name__}, "
        f"expected {expected_type.__name__}"
    )


def test_heuristic_weight_defaults_sum_to_one_per_bloc():
    """Settings defaults must satisfy the HeuristicWeights sum invariants."""
    defaults = Settings.model_fields
    s_sum = (
        defaults["heuristic_w_freshness"].default
        + defaults["heuristic_w_source"].default
        + defaults["heuristic_w_confirmation"].default
        + defaults["heuristic_w_llm"].default
    )
    t_sum = (
        defaults["heuristic_w_liquidity"].default
        + defaults["heuristic_w_spread"].default
        + defaults["heuristic_w_time_to_resolution"].default
    )
    top_sum = (
        defaults["heuristic_strength_weight"].default
        + defaults["heuristic_trade_weight"].default
    )
    assert abs(s_sum - 1.0) < 1e-6, f"strength bloc sums to {s_sum}"
    assert abs(t_sum - 1.0) < 1e-6, f"trade bloc sums to {t_sum}"
    assert abs(top_sum - 1.0) < 1e-6, f"top bloc sums to {top_sum}"


def test_heuristicweights_from_settings_defaults_equals_frozen_v1():
    """Loading weights from Settings defaults must equal HeuristicWeights.frozen_v1()."""
    from app.scoring.weights import HeuristicWeights
    from app.core.config import get_settings

    get_settings.cache_clear()  # ensure we read the latest declaration
    s = get_settings()
    loaded = HeuristicWeights.load_from_settings(s)
    assert loaded == HeuristicWeights.frozen_v1()
