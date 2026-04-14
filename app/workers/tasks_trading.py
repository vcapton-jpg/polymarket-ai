"""Trading worker tasks — position sync, price updates, order monitoring."""

import logging
from datetime import datetime, timezone

from app.workers.celery_app import celery_app
from app.workers._async_helpers import run_async

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks_trading.sync_positions")
def sync_positions():
    """Sync positions and update current prices from Polymarket CLOB."""
    return run_async(_sync_positions_async())


async def _sync_positions_async():
    from sqlalchemy import select
    from app.db.database import get_async_session
    from app.db.models import Portfolio, Position
    from app.polymarket.clob_client import ClobClient

    async with get_async_session() as db:
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
            return {"status": "no_open_positions"}

        clob = ClobClient()
        updated = 0
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
                    updated += 1
        finally:
            await clob.close()

        await db.commit()
        logger.info("Updated prices for %d/%d positions", updated, len(positions))
        return {"status": "ok", "updated": updated, "total": len(positions)}


@celery_app.task(name="app.workers.tasks_trading.check_risk_alerts")
def check_risk_alerts():
    """Run risk manager checks on open positions."""
    return run_async(_check_risk_async())


async def _check_risk_async():
    from sqlalchemy import select
    from app.db.database import get_async_session
    from app.db.models import Portfolio
    from app.agents.risk_manager import risk_manager_agent

    async with get_async_session() as db:
        result = await db.execute(select(Portfolio).limit(1))
        portfolio = result.scalar_one_or_none()
        if not portfolio:
            return {"alerts": []}

        alerts = await risk_manager_agent.check_positions(db, portfolio.id)
        await db.commit()
        return {"alerts_count": len(alerts)}
