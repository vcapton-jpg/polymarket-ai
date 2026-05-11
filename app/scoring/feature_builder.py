"""Feature builder for scoring features."""

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

MAX_LIQUIDITY = 100_000
MAX_VOLUME = 100_000
MAX_SPREAD = 1.0
MAX_HOURS_TO_RESOLUTION = 24 * 365


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class FeatureBuilder:

    def build_freshness_factor(
        self,
        ingestion_date: datetime,
    ) -> float:
        if not ingestion_date:
            return 0.5

        ingestion_date = _ensure_aware(ingestion_date)
        age_hours = (_now_utc() - ingestion_date).total_seconds() / 3600

        if age_hours <= 1:
            return 1.0
        if age_hours <= 6:
            return 0.9
        if age_hours <= 24:
            return 0.7
        if age_hours <= 72:
            return 0.4
        return 0.1

    def build_source_weight(self, source_weight: float) -> float:
        if not source_weight:
            return 0.5
        return min(1.0, source_weight)

    def build_confirmation_factor(self, source_count: int, source_tier: int = 2) -> float:
        if source_count >= 3:
            return 1.0
        if source_count >= 2:
            return 0.85
        if source_tier == 1:
            return 0.7
        return 0.5

    def build_liquidity_factor(self, liquidity: float | None) -> float:
        if not liquidity or liquidity <= 0:
            return 0.1

        if liquidity < 1_000:
            return 0.15
        if liquidity < 10_000:
            return 0.6
        if liquidity <= 100_000:
            return 1.0
        if liquidity <= 500_000:
            return 0.7
        return 0.4

    def build_spread_penalty(self, spread: float | None) -> float:
        if not spread or spread <= 0:
            return 0.8
        if spread <= 0.02:
            return 1.0
        if spread <= 0.05:
            return 0.8
        if spread <= 0.10:
            return 0.5
        return max(0.0, 1.0 - spread / MAX_SPREAD)

    def build_time_to_resolution_factor(
        self,
        end_date: datetime | None,
    ) -> float:
        if not end_date:
            return 0.5

        end_date = _ensure_aware(end_date)
        hours_left = (end_date - _now_utc()).total_seconds() / 3600

        if hours_left <= 0:
            return 1.0
        if hours_left <= 24:
            return 0.95
        if hours_left <= 168:
            return 0.8
        if hours_left <= 720:
            return 0.6
        if hours_left <= MAX_HOURS_TO_RESOLUTION:
            return 0.4
        return 0.2


def create_feature_builder() -> FeatureBuilder:
    return FeatureBuilder()
