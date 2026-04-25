"""Heuristic scorer — now a thin orchestrator over pure sub-scorers.

Chantier #5: the actual math lives in `strength_scorer.py`, `trade_scorer.py`,
and the knobs in `weights.py`. This class preserves the legacy public API
(constructor, `compute_score`, `is_actionable`, `derive_*_label`) so every
existing call-site in `SignalBuilder` works untouched.
"""

import logging

from app.core.config import get_settings
from app.scoring.strength_scorer import compute_signal_strength
from app.scoring.trade_scorer import compute_trade_quality
from app.scoring.weights import HeuristicWeights

logger = logging.getLogger(__name__)


class HeuristicScorer:
    def __init__(self, weights: HeuristicWeights | None = None):
        settings = get_settings()
        self.threshold = settings.signal_score_threshold
        self.weights = weights or HeuristicWeights.load_from_settings(settings)

    def compute_score(
        self,
        features: dict,
        llm_combined: float | None = None,
    ) -> dict:
        """Two-dimensional score: strength + trade → final.

        Output values are int in [0, 100] for backward compatibility with
        existing DB columns (Numeric(5,1)) and UI rendering.
        """
        strength_float = compute_signal_strength(features, self.weights, llm_combined)
        trade_float = compute_trade_quality(features, self.weights)

        signal_strength = max(0, min(100, int(strength_float * 100)))
        trade_quality = max(0, min(100, int(trade_float * 100)))

        raw_final = (
            signal_strength * self.weights.strength_weight
            + trade_quality * self.weights.trade_weight
        )
        signal_score = max(0, min(100, int(raw_final)))

        return {
            "signal_score": signal_score,
            "signal_strength": signal_strength,
            "trade_quality": trade_quality,
        }

    def is_actionable(self, score: int) -> bool:
        return score >= self.threshold

    def derive_confidence_label(self, score: int, source_count: int) -> str:
        # NOTE: source_count is intentionally unused — it already feeds into
        # `confirmation_factor` which is part of `signal_score`. Re-applying
        # a discrete threshold here would double-count source coverage and
        # produce inconsistent labels (e.g. "Signal Fort 80" + "Confiance
        # Moyenne" when only 1 source confirmed).
        if score >= 80:
            return "high"
        if score >= 65:
            return "medium"
        return "low"

    def derive_urgency_label(self, score: int, time_factor: float) -> str:
        if time_factor >= 0.8:
            return "critical"
        if time_factor >= 0.5:
            return "high"
        if time_factor >= 0.2:
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
        if score >= 0.6:
            return "good"
        if score >= 0.4:
            return "fair"
        return "poor"


def create_heuristic_scorer() -> HeuristicScorer:
    return HeuristicScorer()
