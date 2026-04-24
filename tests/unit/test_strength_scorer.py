"""Chantier #5 — strength_scorer pure function.

Each weight in the strength bloc gets two tests:
  - monotone: raising that feature strictly increases the output, others equal
  - zero-weight: if w_key=0, the feature has no effect on output

These pin the contribution of every knob. If a future refactor accidentally
drops a feature or swaps a weight, the corresponding test fails.
"""
from __future__ import annotations

from app.scoring.strength_scorer import compute_signal_strength
from app.scoring.weights import HeuristicWeights


def _neutral_features(**overrides):
    base = {
        "freshness": 0.5,
        "source_weight": 0.5,
        "confirmation": 0.5,
    }
    base.update(overrides)
    return base


# ---- freshness ----------------------------------------------------------

def test_freshness_monotone():
    w = HeuristicWeights()
    low = compute_signal_strength(_neutral_features(freshness=0.0), w, llm_combined=0.5)
    high = compute_signal_strength(_neutral_features(freshness=1.0), w, llm_combined=0.5)
    assert high > low


def test_freshness_zero_weight_eliminates_effect():
    # Redistribute the 0.15 to source to keep sum=1.0
    w = HeuristicWeights(w_freshness=0.0, w_source=0.25, w_confirmation=0.15, w_llm=0.60)
    a = compute_signal_strength(_neutral_features(freshness=0.0), w, llm_combined=0.5)
    b = compute_signal_strength(_neutral_features(freshness=1.0), w, llm_combined=0.5)
    assert a == b


# ---- source_weight ------------------------------------------------------

def test_source_monotone():
    w = HeuristicWeights()
    low = compute_signal_strength(_neutral_features(source_weight=0.0), w, llm_combined=0.5)
    high = compute_signal_strength(_neutral_features(source_weight=1.0), w, llm_combined=0.5)
    assert high > low


def test_source_zero_weight_eliminates_effect():
    w = HeuristicWeights(w_freshness=0.25, w_source=0.0, w_confirmation=0.15, w_llm=0.60)
    a = compute_signal_strength(_neutral_features(source_weight=0.0), w, llm_combined=0.5)
    b = compute_signal_strength(_neutral_features(source_weight=1.0), w, llm_combined=0.5)
    assert a == b


# ---- confirmation -------------------------------------------------------

def test_confirmation_monotone():
    w = HeuristicWeights()
    low = compute_signal_strength(_neutral_features(confirmation=0.0), w, llm_combined=0.5)
    high = compute_signal_strength(_neutral_features(confirmation=1.0), w, llm_combined=0.5)
    assert high > low


def test_confirmation_zero_weight_eliminates_effect():
    w = HeuristicWeights(w_freshness=0.15, w_source=0.25, w_confirmation=0.0, w_llm=0.60)
    a = compute_signal_strength(_neutral_features(confirmation=0.0), w, llm_combined=0.5)
    b = compute_signal_strength(_neutral_features(confirmation=1.0), w, llm_combined=0.5)
    assert a == b


# ---- llm ---------------------------------------------------------------

def test_llm_monotone_when_present():
    w = HeuristicWeights()
    low = compute_signal_strength(_neutral_features(), w, llm_combined=0.0)
    high = compute_signal_strength(_neutral_features(), w, llm_combined=1.0)
    assert high > low


def test_llm_zero_weight_eliminates_effect():
    # Redistribute 0.60 to the three backend weights to keep sum=1.0
    w = HeuristicWeights(w_freshness=0.35, w_source=0.30, w_confirmation=0.35, w_llm=0.0)
    a = compute_signal_strength(_neutral_features(), w, llm_combined=0.0)
    b = compute_signal_strength(_neutral_features(), w, llm_combined=1.0)
    assert a == b


# ---- output bounds ------------------------------------------------------

def test_output_bounded_in_unit_interval():
    w = HeuristicWeights()
    for f_val in (0.0, 0.5, 1.0):
        for llm in (0.0, 0.5, 1.0):
            score = compute_signal_strength(_neutral_features(
                freshness=f_val, source_weight=f_val, confirmation=f_val,
            ), w, llm_combined=llm)
            assert 0.0 <= score <= 1.0, f"{score} out of [0,1] for f={f_val}, llm={llm}"


def test_missing_feature_defaults_to_neutral():
    """Absent keys should behave the same as the legacy scorer: fallback 0.5."""
    w = HeuristicWeights()
    full = compute_signal_strength(
        {"freshness": 0.5, "source_weight": 0.5, "confirmation": 0.5}, w, llm_combined=0.5
    )
    partial = compute_signal_strength({}, w, llm_combined=0.5)
    assert abs(full - partial) < 1e-9


def test_llm_none_renormalizes_backend_contributions():
    """Legacy behaviour (`HeuristicScorer.compute_score(features)` with no
    `llm_combined`): backend contributions are renormalised to the full [0,1]
    range by dividing by (1 - w_llm). Preserve bit-exactness."""
    w = HeuristicWeights()
    # With llm=None, the backend 0.40 bloc is scaled up by 1/(1-0.60) = 2.5.
    features = _neutral_features()
    with_none = compute_signal_strength(features, w, llm_combined=None)
    # Same backend contribution, computed by hand: 0.5*0.15 + 0.5*0.10 + 0.5*0.15 = 0.20
    # Renormalised: 0.20 / 0.40 = 0.50
    assert abs(with_none - 0.50) < 1e-9
