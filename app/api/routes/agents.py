"""Agent status and activity feed API routes."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db_session
from app.db.models import AgentActivity

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])

AGENT_REGISTRY = {
    "scout": {
        "name": "Scout",
        "role": "News surveillance & event detection",
        "icon": "search",
    },
    "analyst": {
        "name": "Analyst",
        "role": "Impact analysis & signal scoring",
        "icon": "brain",
    },
    "strategist": {
        "name": "Strategist",
        "role": "Position sizing & portfolio allocation",
        "icon": "target",
    },
    "trader": {
        "name": "Trader",
        "role": "Trade execution on Polymarket",
        "icon": "zap",
    },
    "risk_manager": {
        "name": "Risk Manager",
        "role": "Position monitoring & risk alerts",
        "icon": "shield",
    },
    "reporter": {
        "name": "Reporter",
        "role": "Daily briefs & performance reports",
        "icon": "file-text",
    },
}


@router.get("/status")
async def get_agents_status(db: AsyncSession = Depends(get_db_session)):
    """Get status of all agents with their latest activity."""
    agents = []
    for agent_id, info in AGENT_REGISTRY.items():
        last_activity = await db.execute(
            select(AgentActivity)
            .where(AgentActivity.agent_name == agent_id)
            .order_by(desc(AgentActivity.created_at))
            .limit(1)
        )
        last = last_activity.scalar_one_or_none()

        count_result = await db.execute(
            select(func.count(AgentActivity.id))
            .where(AgentActivity.agent_name == agent_id)
        )
        total_actions = count_result.scalar() or 0

        agents.append({
            "id": agent_id,
            **info,
            "status": "active" if last else "idle",
            "total_actions": total_actions,
            "last_activity": {
                "action": last.action_type,
                "summary": last.summary,
                "at": last.created_at.isoformat(),
            } if last else None,
        })

    return {"agents": agents}


@router.get("/activity")
async def get_agent_activity(
    agent: str | None = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db_session),
):
    """Get agent activity feed."""
    query = select(AgentActivity).order_by(desc(AgentActivity.created_at))
    if agent:
        query = query.where(AgentActivity.agent_name == agent)
    query = query.limit(limit)

    result = await db.execute(query)
    activities = result.scalars().all()

    return {
        "activities": [
            {
                "id": a.id,
                "agent": a.agent_name,
                "agent_name": AGENT_REGISTRY.get(a.agent_name, {}).get("name", a.agent_name),
                "action": a.action_type,
                "summary": a.summary,
                "details": a.details,
                "at": a.created_at.isoformat(),
            }
            for a in activities
        ],
    }
