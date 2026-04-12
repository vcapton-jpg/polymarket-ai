"""Feature builder for scoring features."""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Constants for feature computation
MAX_LIQUIDITY = 1_000_000
MAX_VOLUME = 1_000_000
MAX_SPREAD = 1.0  # 100%
MAX_HOURS_TO_RESOLUTION = 24 * 30  # 30 days


class FeatureBuilder:
    """Builder for scoring features."""

    def build_freshness_factor(
        self,
        ingestion_date: datetime,
    ) -> float:
        """Build freshness factor from ingestion date.

        Args:
            ingestion_date: Article ingestion date.

        Returns:
            Freshness factor (0-1, higher is fresher).
        """
        if not ingestion_date:
            return 0.5

        age_minutes = (datetime.utcnow() - ingestion_date).total_seconds() / 60

        # Decay over 4 hours
        if age_minutes > 240:
            return 0.0

        return 1.0 - (age_minutes / 240)

    def build_source_weight(self, source_weight: float) -> float:
        """Build source weight factor.

        Args:
            source_weight: Source weight (0-1).

        Returns:
            Source weight factor.
        """
        if not source_weight:
            return 0.5

        return min(1.0, source_weight)

    def build_confirmation_factor(self, source_count: int) -> float:
        """Build confirmation factor from source count.

        Args:
            source_count: Number of sources.

        Returns:
            Confirmation factor (0-1).
        """
        # Linear increase up to 3 sources
        if source_count >= 3:
            return 1.0

        return source_count / 3.0

    def build_liquidity_factor(self, liquidity: Optional[float]) -> float:
        """Build liquidity factor.

        Args:
            liquidity: Market liquidity.

        Returns:
            Liquidity factor (0-1).
        """
        if not liquidity or liquidity <= 0:
            return 0.0

        return min(1.0, liquidity / MAX_LIQUIDITY)

    def build_spread_penalty(self, spread: Optional[float]) -> float:
        """Build spread penalty factor.

        Args:
            spread: Market spread (0-1).

        Returns:
            Spread penalty (0-1, higher spread = lower penalty value).
        """
        if not spread or spread <= 0:
            return 1.0  # No penalty

        # Penalty inversely proportional to spread
        return max(0.0, 1.0 - spread / MAX_SPREAD)

    def build_time_to_resolution_factor(
        self,
        end_date: Optional[datetime],
    ) -> float:
        """Build time to resolution factor.

        Args:
            end_date: Market end date.

        Returns:
            Factor (0-1, higher = more urgent).
        """
        if not end_date:
            return 0.5  # Unknown

        hours_left = (end_date - datetime.utcnow()).total_seconds() / 3600

        if hours_left <= 0:
            return 1.0  # Already resolved

        if hours_left > MAX_HOURS_TO_RESOLUTION:
            return 0.0  # Too far out

        return 1.0 - (hours_left / MAX_HOURS_TO_RESOLUTION)


def create_feature_builder() -> FeatureBuilder:
    """Create a feature builder.

    Returns:
        Configured FeatureBuilder.
    """
    return FeatureBuilder()