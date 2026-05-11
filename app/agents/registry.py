"""Agent registry — central access to all agents."""

from app.agents.analyst import analyst_agent
from app.agents.reporter import reporter_agent
from app.agents.risk_manager import risk_manager_agent
from app.agents.scout import scout_agent
from app.agents.strategist import strategist_agent

AGENTS = {
    "scout": scout_agent,
    "analyst": analyst_agent,
    "strategist": strategist_agent,
    "risk_manager": risk_manager_agent,
    "reporter": reporter_agent,
}


def get_agent(name: str):
    return AGENTS.get(name)


def all_agents():
    return AGENTS
