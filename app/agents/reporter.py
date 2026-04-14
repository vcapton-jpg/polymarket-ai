"""Reporter Agent — generates daily briefs and performance reports."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.db.models import DailyBrief, Signal, SignalOutcome

logger = logging.getLogger(__name__)


class ReporterAgent(BaseAgent):
    agent_name = "reporter"
    agent_role = "Daily briefs & performance reports"

    async def generate_daily_brief(self, db: AsyncSession) -> dict:
        """Generate a daily intelligence brief."""
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(hours=24)

        signals_result = await db.execute(
            select(Signal).where(Signal.created_at >= day_ago).order_by(Signal.signal_score.desc())
        )
        signals = signals_result.scalars().all()

        resolved_result = await db.execute(
            select(SignalOutcome)
            .join(Signal)
            .where(Signal.created_at >= day_ago, SignalOutcome.direction_correct.is_not(None))
        )
        resolved = resolved_result.scalars().all()
        wins = sum(1 for r in resolved if r.direction_correct)

        brief = {
            "date": now.isoformat(),
            "signals_count": len(signals),
            "top_signals": [
                {
                    "id": s.id,
                    "score": float(s.signal_score),
                    "direction": s.direction,
                    "market_id": s.market_id,
                }
                for s in signals[:5]
            ],
            "resolved_count": len(resolved),
            "wins": wins,
            "losses": len(resolved) - wins,
            "win_rate": round(wins / len(resolved) * 100, 1) if resolved else None,
        }

        db_brief = DailyBrief(
            brief_date=now,
            brief_type="daily",
            content=brief,
        )
        db.add(db_brief)

        await self.log_activity(
            db,
            action_type="daily_brief",
            summary=f"Daily brief: {len(signals)} signals, {wins}/{len(resolved)} wins",
            details=brief,
        )

        return brief


reporter_agent = ReporterAgent()
