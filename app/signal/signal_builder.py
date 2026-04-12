"""Signal builder for creating trading signals."""

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Signal, SignalOutcome
from app.scoring.feature_builder import create_feature_builder
from app.scoring.heuristic_scorer import create_heuristic_scorer

logger = logging.getLogger(__name__)


class SignalBuilder:
    """Builder for creating signals."""

    def __init__(self):
        """Initialize the signal builder."""
        self.feature_builder = create_feature_builder()
        self.scorer = create_heuristic_scorer()

    async def build_signal(
        self,
        event_id: int,
        market_id: int,
        event_data: dict,
        market_data: dict,
        llm_analysis: dict | None = None,
    ) -> Signal:
        """Build a signal from event and market data.

        Args:
            event_id: Event ID.
            market_id: Market ID.
            event_data: Event data.
            market_data: Market data.
            llm_analysis: Optional LLM analysis.

        Returns:
            Signal instance.
        """
        # Build features
        features = {
            "freshness": self.feature_builder.build_freshness_factor(
                event_data.get("created_at")
            ),
            "source_weight": self.feature_builder.build_source_weight(
                event_data.get("source_weight", 0.5)
            ),
            "confirmation": self.feature_builder.build_confirmation_factor(
                event_data.get("source_count", 1)
            ),
            "liquidity": self.feature_builder.build_liquidity_factor(
                market_data.get("liquidity")
            ),
            "spread": self.feature_builder.build_spread_penalty(
                market_data.get("spread")
            ),
            "time_to_resolution": self.feature_builder.build_time_to_resolution_factor(
                market_data.get("end_date")
            ),
        }

        # Get LLM impact score
        llm_impact_score = llm_analysis.get("llm_impact_score") if llm_analysis else None

        # Compute score
        score = self.scorer.compute_score(features, llm_impact_score)

        # Determine direction
        direction = "YES"
        if llm_analysis:
            direction = llm_analysis.get("llm_direction", "YES")

        # Derive labels
        confidence_label = self.scorer.derive_confidence_label(
            score, event_data.get("source_count", 1)
        )
        urgency_label = self.scorer.derive_urgency_label(
            score, features.get("time_to_resolution", 0.5)
        )
        tradability_label = self.scorer.derive_tradability_label(
            features.get("liquidity", 0.5), features.get("spread", 1.0)
        )

        # Create signal
        signal = Signal(
            event_id=event_id,
            market_id=market_id,
            score=score,
            direction=direction,
            confidence_label=confidence_label,
            urgency_label=urgency_label,
            tradability_label=tradability_label,
            market_price_at_signal=market_data.get("best_bid"),
            signal_date=datetime.utcnow(),
        )

        return signal


def create_signal_builder() -> SignalBuilder:
    """Create a signal builder.

    Returns:
        Configured SignalBuilder.
    """
    return SignalBuilder()