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
    """Test actionability check."""
    scorer = HeuristicScorer()

    assert scorer.is_actionable(70)
    assert scorer.is_actionable(50)


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