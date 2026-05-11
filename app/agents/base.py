"""Base agent class — all agents inherit from this."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentActivity

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all Signal agents."""

    agent_name: str = "unknown"
    agent_role: str = "Unknown"

    async def log_activity(
        self,
        db: AsyncSession,
        action_type: str,
        summary: str,
        details: dict | None = None,
    ) -> AgentActivity:
        activity = AgentActivity(
            agent_name=self.agent_name,
            action_type=action_type,
            summary=summary,
            details=details,
        )
        db.add(activity)
        await db.flush()
        logger.info("[%s] %s: %s", self.agent_name, action_type, summary)
        return activity

    def get_status(self) -> dict:
        return {
            "agent": self.agent_name,
            "role": self.agent_role,
            "status": "active",
        }
