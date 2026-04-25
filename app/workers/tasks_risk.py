"""Risk monitoring worker tasks."""

import logging

from app.workers.celery_app import celery_app
from app.workers._async_helpers import run_async

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks_risk.monitor_positions")
def monitor_positions():
    """Periodic position monitoring — price updates + risk checks."""
    sync_result = run_async(_monitor_async())
    return sync_result


async def _monitor_async():
    from sqlalchemy import select
    from app.db.database import get_session_factory
    from app.db.models import Portfolio, Position
    from app.polymarket.clob_client import ClobClient
    from app.agents.risk_manager import risk_manager_agent

    async with get_session_factory()() as db:
        result = await db.execute(select(Portfolio).limit(1))
        portfolio = result.scalar_one_or_none()
        if not portfolio:
            return {"status": "no_portfolio"}

        positions_result = await db.execute(
            select(Position).where(
                Position.portfolio_id == portfolio.id,
                Position.status == "open",
            )
        )
        positions = positions_result.scalars().all()
        if not positions:
            return {"status": "no_positions"}

        clob = ClobClient()
        try:
            for pos in positions:
                price = await clob.get_price_yes(pos.market_id)
                if price is not None:
                    pos.current_price = price
                    if pos.entry_price and float(pos.entry_price) > 0:
                        entry = float(pos.entry_price)
                        if pos.side == "BUY":
                            pos.pnl_pct = ((price - entry) / entry) * 100
                        else:
                            pos.pnl_pct = ((entry - price) / entry) * 100
        finally:
            await clob.close()

        alerts = await risk_manager_agent.check_positions(db, portfolio.id)
        await db.commit()

        return {
            "status": "ok",
            "positions_monitored": len(positions),
            "alerts": len(alerts),
        }
