"""Heuristic scorer for signals — two-dimensional: signal_strength + trade_quality."""

import logging
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

STRENGTH_WEIGHT = 0.75
TRADE_WEIGHT = 0.25


class HeuristicScorer:

    def __init__(self):
        self.threshold = settings.signal_score_threshold

        self.strength_weights = {
            "freshness": 0.15,
            "source_weight": 0.10,
            "confirmation": 0.15,
        }
        self.strength_llm_weight = 0.60

        self.trade_weights = {
            "liquidity": 0.40,
            "spread": 0.35,
            "time_to_resolution": 0.25,
        }

    def compute_score(
        self,
        features: dict,
        llm_combined: Optional[float] = None,
    ) -> dict:
        """Compute two-dimensional score.

        Returns dict with signal_strength, trade_quality, and final signal_score.
        """
        strength_base = sum(
            features.get(key, 0.5) * w
            for key, w in self.strength_weights.items()
        )
        if llm_combined is not None:
            strength_raw = strength_base + llm_combined * self.strength_llm_weight
        else:
            strength_raw = strength_base / (1.0 - self.strength_llm_weight)

        signal_strength = max(0, min(100, int(strength_raw * 100)))

        trade_raw = sum(
            features.get(key, 0.5) * w
            for key, w in self.trade_weights.items()
        )
        trade_quality = max(0, min(100, int(trade_raw * 100)))

        signal_score = int(signal_strength * STRENGTH_WEIGHT + trade_quality * TRADE_WEIGHT)
        signal_score = max(0, min(100, signal_score))

        return {
            "signal_score": signal_score,
            "signal_strength": signal_strength,
            "trade_quality": trade_quality,
        }

    def is_actionable(self, score: int) -> bool:
        return score >= self.threshold

    def derive_confidence_label(self, score: int, source_count: int) -> str:
        if score >= 80 and source_count >= 2:
            return "high"
        elif score >= 65:
            return "medium"
        return "low"

    def derive_urgency_label(self, score: int, time_factor: float) -> str:
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
        score = (liquidity_factor * 0.6) + (spread_penalty * 0.4)

        if score >= 0.8:
            return "excellent"
        elif score >= 0.6:
            return "good"
        elif score >= 0.4:
            return "fair"
        return "poor"


def create_heuristic_scorer() -> HeuristicScorer:
    return HeuristicScorer()
