"""Unit tests for heuristic scorer."""

import pytest
from app.scoring.heuristic_scorer import HeuristicScorer


def test_compute_score():
    """Test score computation."""
    scorer = HeuristicScorer()
    
    features = {
        "freshness": 0.9,
        "source_weight": 0.8,
        "confirmation": 0.7,
        "liquidity": 0.6,
        "spread": 0.9,
        "time_to_resolution": 0.5,
    }
    
    result = scorer.compute_score(features)

    assert isinstance(result, dict)
    assert 0 <= result["signal_score"] <= 100


def test_compute_score_with_llm():
    """Test score with LLM impact."""
    scorer = HeuristicScorer()

    features = {
        "freshness": 0.5,
        "source_weight": 0.5,
        "confirmation": 0.5,
        "liquidity": 0.5,
        "spread": 0.5,
        "time_to_resolution": 0.5,
    }

    result = scorer.compute_score(features, llm_combined=0.8)

    assert 0 <= result["signal_score"] <= 100


def test_is_actionable():
    """Test actionability check.

    The threshold is `settings.signal_score_threshold` (default=65 since
    PR #6 raised it from 55). The test must reflect the current default
    or it silently asserts the wrong invariant.
    """
    scorer = HeuristicScorer()

    assert scorer.is_actionable(scorer.threshold + 5)
    assert scorer.is_actionable(scorer.threshold)
    assert not scorer.is_actionable(scorer.threshold - 1)


def test_derive_confidence_label():
    """Test confidence label."""
    scorer = HeuristicScorer()
    
    assert scorer.derive_confidence_label(85, 3) == "high"
    assert scorer.derive_confidence_label(65, 1) == "medium"
    assert scorer.derive_confidence_label(45, 1) == "low"


def test_derive_urgency_label():
    """Test urgency label."""
    scorer = HeuristicScorer()
    
    assert scorer.derive_urgency_label(85, 0.9) == "critical"
    assert scorer.derive_urgency_label(60, 0.6) == "high"
    assert scorer.derive_urgency_label(40, 0.3) == "medium"
    assert scorer.derive_urgency_label(20, 0.1) == "low"


def test_derive_tradability_label():
    """Test tradability label."""
    scorer = HeuristicScorer()
    
    assert scorer.derive_tradability_label(0.9, 0.9) == "excellent"
    assert scorer.derive_tradability_label(0.7, 0.6) == "good"
    assert scorer.derive_tradability_label(0.5, 0.4) == "fair"
    assert scorer.derive_tradability_label(0.2, 0.2) == "poor"


def test_compute_score_matches_hand_computed_values():
    """Pins the exact numeric output for a deterministic feature vector.

    After the refactor (task 4), these numbers must not drift. If you change
    the formula in a later chantier, explicitly update these constants.
    """
    from app.scoring.heuristic_scorer import HeuristicScorer
    scorer = HeuristicScorer()
    features = {
        "freshness": 0.8, "source_weight": 0.6, "confirmation": 0.7,
        "liquidity": 0.9, "spread": 0.4, "time_to_resolution": 0.5,
    }
    result = scorer.compute_score(features, llm_combined=0.75)
    # strength_base = 0.8*0.15 + 0.6*0.10 + 0.7*0.15 = 0.285
    # strength_raw = 0.285 + 0.75*0.60 = 0.735 → int(73.5) = 73
    # trade_raw    = 0.9*0.40 + 0.4*0.35 + 0.5*0.25 = 0.625 → int(62.5) = 62
    # signal_score = int(73*0.75 + 62*0.25) = int(70.25) = 70
    assert result["signal_strength"] == 73
    assert result["trade_quality"] == 62
    assert result["signal_score"] == 70


def test_compute_score_without_llm_renormalises():
    from app.scoring.heuristic_scorer import HeuristicScorer
    scorer = HeuristicScorer()
    features = {
        "freshness": 0.5, "source_weight": 0.5, "confirmation": 0.5,
        "liquidity": 0.5, "spread": 0.5, "time_to_resolution": 0.5,
    }
    result = scorer.compute_score(features)  # no llm_combined
    # strength_base = 0.5*(0.15+0.10+0.15) = 0.20
    # With llm=None: 0.20 / (1-0.60) = 0.50 → int(50) = 50
    # trade_raw = 0.5 → int(50) = 50
    # signal_score = int(50*0.75 + 50*0.25) = 50
    assert result["signal_strength"] == 50
    assert result["trade_quality"] == 50
    assert result["signal_score"] == 50