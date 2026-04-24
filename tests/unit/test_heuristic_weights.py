# tests/unit/test_heuristic_weights.py
"""Chantier #5 — HeuristicWeights invariants.

These tests pin the sum-to-1 contract: if anyone edits the defaults and the
sums drift, the dataclass raises at construction so we never silently score
with a malformed weight vector in prod.
"""
from __future__ import annotations

import pytest

from app.scoring.weights import HeuristicWeights


def test_defaults_match_frozen_v1_values():
    w = HeuristicWeights()
    assert w.w_freshness == 0.15
    assert w.w_source == 0.10
    assert w.w_confirmation == 0.15
    assert w.w_llm == 0.60
    assert w.w_liquidity == 0.40
    assert w.w_spread == 0.35
    assert w.w_time_to_resolution == 0.25
    assert w.strength_weight == 0.75
    assert w.trade_weight == 0.25


def test_strength_bloc_must_sum_to_one():
    # 0.15 + 0.10 + 0.15 + 0.60 = 1.00 ✓ (default)
    HeuristicWeights()  # no raise

    with pytest.raises(ValueError, match="strength_weights sum"):
        HeuristicWeights(w_freshness=0.20)  # 1.05 total


def test_trade_bloc_must_sum_to_one():
    with pytest.raises(ValueError, match="trade_weights sum"):
        HeuristicWeights(w_liquidity=0.50)  # 1.10 total


def test_top_level_must_sum_to_one():
    with pytest.raises(ValueError, match="top_weights sum"):
        HeuristicWeights(strength_weight=0.80)  # 1.05 total


def test_frozen_v1_classmethod_returns_defaults():
    assert HeuristicWeights.frozen_v1() == HeuristicWeights()


def test_dataclass_is_frozen():
    w = HeuristicWeights()
    with pytest.raises(Exception):  # dataclasses.FrozenInstanceError subclasses AttributeError
        w.w_freshness = 0.99  # type: ignore[misc]


def test_load_from_settings_uses_override_values():
    class _FakeSettings:
        heuristic_w_freshness = 0.30
        heuristic_w_source = 0.05
        heuristic_w_confirmation = 0.05
        heuristic_w_llm = 0.60
        # others fall through to defaults

    w = HeuristicWeights.load_from_settings(_FakeSettings())
    assert w.w_freshness == 0.30
    assert w.w_source == 0.05
    assert w.w_llm == 0.60       # explicit override = default value is fine
    assert w.w_liquidity == 0.40  # default


def test_load_from_settings_missing_attr_falls_back_to_default():
    class _Empty:
        pass
    w = HeuristicWeights.load_from_settings(_Empty())
    assert w == HeuristicWeights()  # all defaults
