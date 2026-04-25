"""Report generation worker tasks — daily briefs, weekly reports."""

import logging

from app.workers.celery_app import celery_app
from app.workers._async_helpers import run_async

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks_reports.generate_daily_brief")
def generate_daily_brief():
    """Generate and store the daily intelligence brief."""
    return run_async(_generate_daily_async())


async def _generate_daily_async():
    from app.db.database import get_session_factory
    from app.agents.reporter import reporter_agent

    async with get_session_factory()() as db:
        brief = await reporter_agent.generate_daily_brief(db)
        await db.commit()
        logger.info("Daily brief generated: %d signals", brief.get("signals_count", 0))
        return {"status": "ok", "brief": brief}


@celery_app.task(name="app.workers.tasks_reports.send_telegram_brief")
def send_telegram_brief():
    """Send the latest daily brief via Telegram."""
    return run_async(_send_telegram_brief_async())


async def _send_telegram_brief_async():
    import httpx
    from sqlalchemy import desc, select
    from app.core.config import get_settings
    from app.db.database import get_session_factory
    from app.db.models import DailyBrief

    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return {"status": "telegram_not_configured"}

    async with get_session_factory()() as db:
        result = await db.execute(
            select(DailyBrief).order_by(desc(DailyBrief.created_at)).limit(1)
        )
        brief = result.scalar_one_or_none()
        if not brief:
            return {"status": "no_brief"}

        content = brief.content
        text = (
            f"📊 *Daily Intelligence Brief*\n\n"
            f"Signals today: {content.get('signals_count', 0)}\n"
            f"Resolved: {content.get('resolved_count', 0)} "
            f"({content.get('wins', 0)}W / {content.get('losses', 0)}L)\n"
        )
        wr = content.get("win_rate")
        if wr is not None:
            text += f"Win rate: {wr}%\n"

        top = content.get("top_signals", [])
        if top:
            text += "\n*Top Signals:*\n"
            for s in top[:3]:
                text += f"• #{s['id']} {s['direction']} (score {s['score']:.0f})\n"

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json={
            "chat_id": settings.telegram_chat_id,
            "text": text,
            "parse_mode": "Markdown",
        })
        return {"status": "sent" if resp.status_code == 200 else "failed"}
