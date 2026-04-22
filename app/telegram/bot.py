"""Telegram Bot — full command interface for Signal platform."""

import logging
from typing import Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
BOT_TOKEN = settings.telegram_bot_token
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None


async def send_message(chat_id: str, text: str, parse_mode: str = "Markdown") -> bool:
    if not API_URL:
        return False
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{API_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        })
        return resp.status_code == 200


async def handle_command(chat_id: str, command: str, args: list[str]) -> str:
    """Process a bot command and return the response text."""
    if command == "/start":
        return (
            "Welcome to *Foresight* — Prediction Market Intelligence 🔺\n\n"
            f"Your Chat ID is: `{chat_id}`\n"
            "Copy this ID into Foresight Settings to receive signal alerts.\n\n"
            "Available commands:\n"
            "/signals — Latest trading signals\n"
            "/portfolio — Your positions & P&L\n"
            "/brief — Latest daily intelligence brief\n"
            "/agents — Agent team status\n"
            "/help — Show this message"
        )

    elif command == "/signals":
        return await _cmd_signals()

    elif command == "/portfolio":
        return await _cmd_portfolio()

    elif command == "/brief":
        return await _cmd_brief()

    elif command == "/agents":
        return await _cmd_agents()

    elif command == "/help":
        return (
            "*Foresight Bot Commands*\n\n"
            "/signals — Top 5 latest signals\n"
            "/portfolio — Current positions\n"
            "/brief — Daily intelligence brief\n"
            "/agents — Agent status overview\n\n"
            f"Your Chat ID: `{chat_id}`"
        )

    return "Unknown command. Type /help for available commands."


async def _cmd_signals() -> str:
    from app.db.database import get_async_session
    from sqlalchemy import desc, select
    from app.db.models import Signal

    async with get_async_session() as db:
        result = await db.execute(
            select(Signal).order_by(desc(Signal.created_at)).limit(5)
        )
        signals = result.scalars().all()

    if not signals:
        return "No signals available."

    lines = ["*Latest Signals*\n"]
    for s in signals:
        emoji = "🟢" if "YES" in s.direction else "🔴"
        lines.append(
            f"{emoji} #{s.id} | {s.direction} | Score: {float(s.signal_score):.0f}"
        )
    return "\n".join(lines)


async def _cmd_portfolio() -> str:
    from app.db.database import get_async_session
    from sqlalchemy import select
    from app.db.models import Portfolio, Position

    async with get_async_session() as db:
        result = await db.execute(select(Portfolio).limit(1))
        portfolio = result.scalar_one_or_none()
        if not portfolio:
            return "No portfolio found. Start trading from the dashboard!"

        pos_result = await db.execute(
            select(Position).where(
                Position.portfolio_id == portfolio.id,
                Position.status == "open",
            )
        )
        positions = pos_result.scalars().all()

    lines = [
        f"*Portfolio*\n",
        f"Total Value: ${float(portfolio.total_value):,.2f}",
        f"Cash: ${float(portfolio.cash_balance):,.2f}",
        f"Open Positions: {len(positions)}\n",
    ]

    for p in positions[:5]:
        pnl = float(p.pnl_pct) if p.pnl_pct else 0
        emoji = "📈" if pnl >= 0 else "📉"
        lines.append(f"{emoji} {p.side} {p.market_id[:20]}… | P&L: {pnl:+.1f}%")

    return "\n".join(lines)


async def _cmd_brief() -> str:
    from app.db.database import get_async_session
    from sqlalchemy import desc, select
    from app.db.models import DailyBrief

    async with get_async_session() as db:
        result = await db.execute(
            select(DailyBrief).order_by(desc(DailyBrief.created_at)).limit(1)
        )
        brief = result.scalar_one_or_none()

    if not brief:
        return "No daily brief available yet."

    c = brief.content
    lines = [
        "*Daily Intelligence Brief*\n",
        f"Signals: {c.get('signals_count', 0)}",
        f"Resolved: {c.get('resolved_count', 0)} ({c.get('wins', 0)}W / {c.get('losses', 0)}L)",
    ]
    wr = c.get("win_rate")
    if wr is not None:
        lines.append(f"Win Rate: {wr}%")

    return "\n".join(lines)


async def _cmd_agents() -> str:
    from app.db.database import get_async_session
    from sqlalchemy import desc, func, select
    from app.db.models import AgentActivity

    agent_names = ["scout", "analyst", "strategist", "trader", "risk_manager", "reporter"]

    async with get_async_session() as db:
        lines = ["*Agent Team Status*\n"]
        for name in agent_names:
            count_result = await db.execute(
                select(func.count(AgentActivity.id))
                .where(AgentActivity.agent_name == name)
            )
            total = count_result.scalar() or 0
            emoji = "🟢" if total > 0 else "⚪"
            lines.append(f"{emoji} {name.replace('_', ' ').title()} — {total} actions")

    return "\n".join(lines)
