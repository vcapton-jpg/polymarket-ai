"""Strategist Agent — position sizing and portfolio allocation."""

import logging
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.db.models import Position

logger = logging.getLogger(__name__)

MAX_POSITION_PCT = 0.10
MAX_BUCKET_CONCENTRATION = 0.30
KELLY_FRACTION = 0.25


class StrategistAgent(BaseAgent):
    agent_name = "strategist"
    agent_role = "Position sizing & portfolio allocation"

    async def recommend_size(
        self,
        db: AsyncSession,
        portfolio_id: int,
        portfolio_value: float,
        signal_score: float,
        signal_strength: float,
        market_price: float,
        direction: str,
        bucket: Optional[str] = None,
    ) -> dict:
        """Recommend position size based on Kelly criterion and concentration limits."""
        edge = (signal_strength / 100) * abs(0.5 - market_price) * 2
        kelly_size = portfolio_value * edge * KELLY_FRACTION
        max_position = portfolio_value * MAX_POSITION_PCT
        recommended = min(kelly_size, max_position)

        if bucket:
            bucket_exposure = await self._get_bucket_exposure(db, portfolio_id, bucket)
            bucket_limit = portfolio_value * MAX_BUCKET_CONCENTRATION
            remaining = max(0, bucket_limit - bucket_exposure)
            recommended = min(recommended, remaining)

        recommended = max(1.0, round(recommended, 2))

        reason = f"Edge {edge:.2%}, Kelly suggests ${kelly_size:.0f}, capped at ${recommended:.0f}"
        await self.log_activity(
            db,
            action_type="sizing_recommendation",
            summary=f"Recommends ${recommended:.0f} on {direction} (edge {edge:.1%})",
            details={
                "edge": round(edge, 4),
                "kelly_raw": round(kelly_size, 2),
                "recommended": round(recommended, 2),
                "reason": reason,
            },
        )

        return {
            "recommended_size": round(recommended, 2),
            "edge": round(edge, 4),
            "reason": reason,
        }

    async def _get_bucket_exposure(
        self, db: AsyncSession, portfolio_id: int, bucket: str,
    ) -> float:
        from app.db.models import Market
        result = await db.execute(
            select(func.coalesce(func.sum(Position.size * Position.entry_price), 0))
            .join(Market, Position.market_id == Market.market_id)
            .where(
                Position.portfolio_id == portfolio_id,
                Position.status == "open",
                Market.bucket == bucket,
            )
        )
        return float(result.scalar() or 0)


strategist_agent = StrategistAgent()
