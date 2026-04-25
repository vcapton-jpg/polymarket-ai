"""Pure replay of the 6 backtestable rejection gates.

These functions mirror the prod gates in `app.signal.signal_builder.SignalBuilder.build_signal`
([signal_builder.py:122-167](../../../app/signal/signal_builder.py)). Replay
is a *mirror*, not a re-import: a future change in prod must trigger a
test failure here so the audit report doesn't silently drift.

Each gate returns `GateResult(passed: bool, reason: str | None)`. Numeric
gates accept a `threshold` parameter so the backtest runner can sweep
counterfactual values (± 0.05, ± 0.10) without forking the gate logic.
"""
from __future__ import annotations

import pytest

from app.scoring.gate_replay import (
    GateInput,
    GateResult,
    gate_ambiguity,
    gate_cosine,
    gate_direction_clear,
    gate_has_reasoning,
    gate_impact_strength,
    gate_specificity,
    replay_all_gates,
)

# ── gate_cosine ──────────────────────────────────────────────────────────


def test_gate_cosine_passes_above_threshold():
    res = gate_cosine(GateInput(cosine_score=0.60), threshold=0.52)
    assert res.passed is True
    assert res.reason is None


def test_gate_cosine_fails_below_threshold():
    res = gate_cosine(GateInput(cosine_score=0.40), threshold=0.52)
    assert res.passed is False
    assert "cosine" in res.reason


def test_gate_cosine_passes_when_score_is_none():
    """Mirror prod: signal_builder.py only fails on `cosine is not None and < threshold`.
    A NULL cosine is NOT a rejection — common when the cosine join is missing.
    """
    res = gate_cosine(GateInput(cosine_score=None), threshold=0.52)
    assert res.passed is True


def test_gate_cosine_threshold_inclusive_at_boundary():
    """Exactly at threshold is a pass (prod uses `< threshold`, not `<=`)."""
    res = gate_cosine(GateInput(cosine_score=0.52), threshold=0.52)
    assert res.passed is True


# ── gate_direction_clear ─────────────────────────────────────────────────


def test_gate_direction_clear_passes_with_buy_yes():
    res = gate_direction_clear(GateInput(impact_direction="BUY_YES"))
    assert res.passed is True


def test_gate_direction_clear_passes_with_buy_no():
    res = gate_direction_clear(GateInput(impact_direction="BUY_NO"))
    assert res.passed is True


@pytest.mark.parametrize("direction", ["NEUTRAL", "UNCLEAR", "", None])
def test_gate_direction_clear_fails_on_unclear_or_missing(direction):
    res = gate_direction_clear(GateInput(impact_direction=direction))
    assert res.passed is False
    assert "direction" in res.reason


def test_gate_direction_clear_handles_lowercase_input():
    """Prod uppercases the input — replay must match."""
    res = gate_direction_clear(GateInput(impact_direction="buy_yes"))
    assert res.passed is True


# ── gate_ambiguity ───────────────────────────────────────────────────────


def test_gate_ambiguity_passes_when_below_threshold():
    res = gate_ambiguity(GateInput(ambiguity_score=0.30), threshold=0.80)
    assert res.passed is True


def test_gate_ambiguity_fails_above_threshold():
    res = gate_ambiguity(GateInput(ambiguity_score=0.90), threshold=0.80)
    assert res.passed is False
    assert "ambiguity" in res.reason


def test_gate_ambiguity_passes_when_score_is_none():
    """Prod skips the gate when ambiguity is None — keeps the pair alive."""
    res = gate_ambiguity(GateInput(ambiguity_score=None), threshold=0.80)
    assert res.passed is True


# ── gate_specificity ─────────────────────────────────────────────────────


def test_gate_specificity_passes_when_above_threshold():
    res = gate_specificity(GateInput(specificity_score=0.80), threshold=0.40)
    assert res.passed is True


def test_gate_specificity_fails_below_threshold():
    res = gate_specificity(GateInput(specificity_score=0.20), threshold=0.40)
    assert res.passed is False
    assert "specificity" in res.reason


def test_gate_specificity_passes_when_none():
    res = gate_specificity(GateInput(specificity_score=None), threshold=0.40)
    assert res.passed is True


# ── gate_impact_strength ─────────────────────────────────────────────────


def test_gate_impact_strength_passes_when_positive():
    res = gate_impact_strength(GateInput(impact_strength=0.5))
    assert res.passed is True


def test_gate_impact_strength_fails_when_zero():
    """Prod: `if strength is None or float(strength) == 0` → reject."""
    res = gate_impact_strength(GateInput(impact_strength=0.0))
    assert res.passed is False
    assert "impact_strength" in res.reason


def test_gate_impact_strength_fails_when_none():
    res = gate_impact_strength(GateInput(impact_strength=None))
    assert res.passed is False


# ── gate_has_reasoning ───────────────────────────────────────────────────


def test_gate_has_reasoning_passes_with_text():
    res = gate_has_reasoning(GateInput(reasoning="The catalyst confirms..."))
    assert res.passed is True


def test_gate_has_reasoning_fails_when_none():
    res = gate_has_reasoning(GateInput(reasoning=None))
    assert res.passed is False
    assert "reasoning" in res.reason


def test_gate_has_reasoning_fails_on_empty_string():
    """Whitespace-only reasoning is not actionable — treat as missing."""
    res = gate_has_reasoning(GateInput(reasoning="   "))
    assert res.passed is False


# ── replay_all_gates ─────────────────────────────────────────────────────


def test_replay_all_gates_returns_six_decisions():
    """The aggregator runs all 6 gates and returns a per-gate decision dict."""
    result = replay_all_gates(GateInput(
        cosine_score=0.60,
        impact_direction="BUY_YES",
        ambiguity_score=0.20,
        specificity_score=0.80,
        impact_strength=0.7,
        reasoning="Reuters confirms the development.",
    ))
    assert set(result.keys()) == {
        "cosine", "direction_clear", "ambiguity",
        "specificity", "impact_strength", "has_reasoning",
    }
    for r in result.values():
        assert isinstance(r, GateResult)
        assert r.passed is True


def test_replay_all_gates_isolates_failures():
    """One failing gate does not short-circuit the others — the runner needs the
    full per-gate decision tuple to attribute rejection blame correctly.
    """
    result = replay_all_gates(GateInput(
        cosine_score=0.40,           # fails
        impact_direction="BUY_YES",  # passes
        ambiguity_score=0.95,        # fails
        specificity_score=0.80,      # passes
        impact_strength=0.7,         # passes
        reasoning="ok",              # passes
    ))
    assert result["cosine"].passed is False
    assert result["ambiguity"].passed is False
    assert result["direction_clear"].passed is True
    assert result["specificity"].passed is True
    assert result["impact_strength"].passed is True
    assert result["has_reasoning"].passed is True


def test_replay_all_gates_uses_default_thresholds_matching_prod():
    """Prod defaults: cosine 0.52, ambiguity 0.80, specificity 0.40.
    A pair just under each default must fail under the default thresholds.
    """
    result = replay_all_gates(GateInput(
        cosine_score=0.51,           # just below 0.52
        impact_direction="BUY_YES",
        ambiguity_score=0.81,        # just above 0.80
        specificity_score=0.39,      # just below 0.40
        impact_strength=0.7,
        reasoning="ok",
    ))
    assert result["cosine"].passed is False
    assert result["ambiguity"].passed is False
    assert result["specificity"].passed is False
