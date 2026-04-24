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
