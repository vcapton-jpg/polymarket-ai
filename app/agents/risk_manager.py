"""Risk Manager Agent — monitors positions and alerts on adverse moves."""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.db.models import Position

logger = logging.getLogger(__name__)

ALERT_THRESHOLD_PCT = -10.0
TAKE_PROFIT_PCT = 25.0


class RiskManagerAgent(BaseAgent):
    agent_name = "risk_manager"
    agent_role = "Position monitoring & risk alerts"

    async def check_positions(self, db: AsyncSession, portfolio_id: int) -> list[dict]:
        """Check all open positions for risk alerts."""
        result = await db.execute(
            select(Position).where(
                Position.portfolio_id == portfolio_id,
                Position.status == "open",
            )
        )
        positions = result.scalars().all()
        alerts = []

        for pos in positions:
            if pos.pnl_pct is None:
                continue

            pnl = float(pos.pnl_pct)

            if pnl <= ALERT_THRESHOLD_PCT:
                alert = {
                    "type": "stop_loss",
                    "position_id": pos.id,
                    "market_id": pos.market_id,
                    "pnl_pct": pnl,
                    "message": f"Position down {pnl:.1f}% — consider reducing exposure",
                }
                alerts.append(alert)
                await self.log_activity(
                    db,
                    action_type="risk_alert",
                    summary=f"ALERT: Position on {pos.market_id[:20]}… down {pnl:.1f}%",
                    details=alert,
                )

            elif pnl >= TAKE_PROFIT_PCT:
                alert = {
                    "type": "take_profit",
                    "position_id": pos.id,
                    "market_id": pos.market_id,
                    "pnl_pct": pnl,
                    "message": f"Position up {pnl:.1f}% — consider taking profit",
                }
                alerts.append(alert)
                await self.log_activity(
                    db,
                    action_type="take_profit_alert",
                    summary=f"Position on {pos.market_id[:20]}… up {pnl:.1f}% — take profit?",
                    details=alert,
                )

        return alerts


risk_manager_agent = RiskManagerAgent()
