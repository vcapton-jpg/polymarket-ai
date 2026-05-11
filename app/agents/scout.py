"""Scout Agent — wraps the ingestion pipeline with agent personality."""

import logging

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class ScoutAgent(BaseAgent):
    agent_name = "scout"
    agent_role = "News surveillance & event detection"

    async def report_ingestion(self, db, source_name: str, articles_count: int):
        if articles_count > 0:
            await self.log_activity(
                db,
                action_type="ingestion",
                summary=f"Ingested {articles_count} articles from {source_name}",
                details={"source": source_name, "count": articles_count},
            )

    async def report_event_detected(self, db, event_title: str, sources_count: int):
        await self.log_activity(
            db,
            action_type="event_detected",
            summary=f"New event: {event_title} ({sources_count} sources)",
            details={"event_title": event_title, "sources": sources_count},
        )


scout_agent = ScoutAgent()
