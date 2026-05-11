"""Pin the `_build_llm_data` contract — T-011.

The 2026-05-11 audit on prod found 732/732 signals with NULL
`llm_model_version` because the column never propagated through
`event_market_analysis → _build_llm_data → SignalBuilder → Signal`.
This test pins the propagation so a future regression is caught at CI
time, not at month-end when we want to split RTP by model.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.workers.tasks_scoring import _build_llm_data


def _row(**overrides) -> SimpleNamespace:
    """Minimal `EventMarketAnalysis`-like object — all the attrs the
    builder reads, defaulted to None so each test only overrides what
    it asserts on."""
    base = dict(
        impact_direction=None,
        impact_strength=None,
        llm_confidence=None,
        ambiguity_score=None,
        specificity_score=None,
        llm_model_version=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_build_llm_data_returns_none_on_missing_analysis():
    assert _build_llm_data(None) is None


def test_build_llm_data_propagates_llm_model_version():
    """The whole point of T-011: a populated analysis row must surface
    its model version in the dict consumed by SignalBuilder."""
    row = _row(impact_direction="BUY_YES", llm_model_version="gpt-4o-mini")
    out = _build_llm_data(row)
    assert out is not None
    assert out["llm_model_version"] == "gpt-4o-mini"
    assert out["impact_direction"] == "BUY_YES"


def test_build_llm_data_preserves_none_model_version_for_legacy_rows():
    """Legacy rows pre-migration 032 have NULL llm_model_version.
    The builder must accept that without dropping the row."""
    row = _row(impact_direction="BUY_NO", llm_model_version=None)
    out = _build_llm_data(row)
    assert out is not None
    assert out["llm_model_version"] is None


def test_build_llm_data_preserves_zero_scores():
    """Audit 2026-04-25 — zeros must not be coerced to None. Guard
    against a future refactor accidentally regressing on this."""
    row = _row(
        impact_strength=0.0,
        llm_confidence=0.0,
        ambiguity_score=0.0,
        specificity_score=0.0,
    )
    out = _build_llm_data(row)
    assert out["impact_strength"] == 0.0
    assert out["llm_confidence"] == 0.0
    assert out["ambiguity_score"] == 0.0
    assert out["specificity_score"] == 0.0
