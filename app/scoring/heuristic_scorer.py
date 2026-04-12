"""Heuristic scorer for signals."""

import logging
from typing import Optional

from app.core.config import get_settings
from app.scoring.feature_builder import create_feature_builder

logger = logging.getLogger(__name__)
settings = get_settings()


class HeuristicScorer:
    """Heuristic scorer for signal generation."""

    def __init__(self):
        """Initialize the scorer."""
        self.feature_builder = create_feature_builder()
        self.threshold = settings.signal_score_threshold

        # Weights for each feature
        self.weights = {
            "freshness": 0.2,
            "source_weight": 0.15,
            "confirmation": 0.15,
            "liquidity": 0.2,
            "spread": 0.15,
            "time_to_resolution": 0.15,
        }

    def compute_score(self, features: dict, llm_impact_score: Optional[int] = None) -> int:
        """Compute signal score.

        Args:
            features: Feature dictionary.
            llm_impact_score: Optional LLM impact score (0-100).

        Returns:
            Signal score (0-100).
        """
        # Base score from features
        score = sum(
            features.get(key, 0.5) * weight
            for key, weight in self.weights.items()
        )

        # Add LLM impact if available
        if llm_impact_score is not None:
            score = (score * 0.6) + (llm_impact_score * 0.4)

        # Scale to 0-100
        score = int(score * 100)

        return max(0, min(100, score))

    def is_actionable(self, score: int) -> bool:
        """Check if score is actionable.

        Args:
            score: Signal score.

        Returns:
            True if actionable (score >= threshold).
        """
        return score >= self.threshold

    def derive_confidence_label(self, score: int, source_count: int) -> str:
        """Derive confidence label.

        Args:
            score: Signal score.
            source_count: Number of sources.

        Returns:
            Confidence label.
        """
        if score >= 80 and source_count >= 2:
            return "high"
        elif score >= 60 and source_count >= 1:
            return "medium"
        return "low"

    def derive_urgency_label(self, score: int, time_factor: float) -> str:
        """Derive urgency label.

        Args:
            score: Signal score.
            time_factor: Time to resolution factor.

        Returns:
            Urgency label.
        """
        if time_factor >= 0.8:
            return "critical"
        elif time_factor >= 0.5:
            return "high"
        elif time_factor >= 0.2:
            return "medium"
        return "low"

    def derive_tradability_label(
        self,
        liquidity_factor: float,
        spread_penalty: float,
    ) -> str:
        """Derive tradability label.

        Args:
            liquidity_factor: Liquidity factor.
            spread_penalty: Spread penalty.

        Returns:
            Tradability label.
        """
        score = (liquidity_factor * 0.6) + (spread_penalty * 0.4)

        if score >= 0.8:
            return "excellent"
        elif score >= 0.6:
            return "good"
        elif score >= 0.4:
            return "fair"
        return "poor"


def create_heuristic_scorer() -> HeuristicScorer:
    """Create a heuristic scorer.

    Returns:
        Configured HeuristicScorer.
    """
    return HeuristicScorer()