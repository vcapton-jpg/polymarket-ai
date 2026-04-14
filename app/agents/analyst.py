"""Analyst Agent — wraps the scoring/impact analysis pipeline."""

import logging
from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class AnalystAgent(BaseAgent):
    agent_name = "analyst"
    agent_role = "Impact analysis & signal scoring"

    async def report_signal_created(
        self, db, signal_id: int, score: float, direction: str,
        market_question: str, signal_strength: float = None,
    ):
        await self.log_activity(
            db,
            action_type="signal_created",
            summary=f"Signal #{signal_id}: {direction} on '{market_question[:60]}' (score {score:.0f})",
            details={
                "signal_id": signal_id,
                "score": score,
                "direction": direction,
                "signal_strength": signal_strength,
                "market": market_question[:100],
            },
        )

    async def report_analysis_complete(
        self, db, event_title: str, markets_analyzed: int, signals_generated: int,
    ):
        await self.log_activity(
            db,
            action_type="analysis_complete",
            summary=f"Analyzed '{event_title[:50]}' across {markets_analyzed} markets → {signals_generated} signal(s)",
            details={
                "event": event_title[:100],
                "markets_analyzed": markets_analyzed,
                "signals_generated": signals_generated,
            },
        )


analyst_agent = AnalystAgent()
