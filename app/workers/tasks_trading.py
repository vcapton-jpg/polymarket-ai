"""Trading worker tasks — position sync, price updates, order monitoring."""

import logging
from datetime import UTC, datetime

from app.workers._async_helpers import run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks_trading.sync_positions")
def sync_positions():
    """Sync positions and update current prices from Polymarket CLOB."""
    return run_async(_sync_positions_async())


async def _sync_positions_async():
    from sqlalchemy import select

    from app.db.database import get_session_factory
    from app.db.models import Portfolio, Position
    from app.polymarket.clob_client import ClobClient

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


@celery_app.task(name="app.workers.tasks_trading.poll_order_fills")
def poll_order_fills():
    """Poll Polymarket for submitted orders and mark filled ones, then create positions."""
    return run_async(_poll_order_fills_async())


async def _poll_order_fills_async():
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.db.database import get_session_factory
    from app.db.models import Order, Portfolio
    from app.trading.builder_client import BuilderTradeClient
    from app.trading.position_tracker import sync_positions_from_orders

    async with get_session_factory()() as db:
        result = await db.execute(select(Portfolio).limit(1))
        portfolio = result.scalar_one_or_none()
        if not portfolio:
            return {"status": "no_portfolio"}

        submitted = await db.execute(
            select(Order)
            .where(
                Order.portfolio_id == portfolio.id,
                Order.status == "submitted",
                Order.polymarket_order_id.isnot(None),
            )
            .options(selectinload(Order.portfolio).selectinload(Portfolio.user))
        )
        orders = submitted.scalars().all()
        if not orders:
            return {"status": "no_submitted_orders"}

        clients: dict[str, BuilderTradeClient] = {}
        filled_count = 0
        for order in orders:
            safe = order.portfolio.user.polymarket_safe_address if order.portfolio and order.portfolio.user else None
            if not safe:
                logger.warning("Skipping order %s — user has no Safe address", order.polymarket_order_id)
                continue
            if safe not in clients:
                clients[safe] = BuilderTradeClient(safe_address=safe)
            client = clients[safe]
            try:
                data = await client.get_order(order.polymarket_order_id)
                if not data:
                    continue
                status = (data.get("status") or "").upper()
                # MATCHED = fully filled, PARTIALLY_FILLED = partial
                if status in ("MATCHED", "FILLED"):
                    order.status = "filled"
                    order.filled_at = datetime.now(UTC)
                    order.filled_price = float(data.get("price") or order.price)
                    order.filled_size = float(data.get("size_matched") or data.get("size") or order.size)
                    filled_count += 1
                elif status in ("CANCELLED", "CANCELED"):
                    order.status = "cancelled"
            except Exception as e:
                logger.warning("poll_order_fills error for %s: %s", order.polymarket_order_id, e)

        if filled_count > 0:
            await db.flush()
            await sync_positions_from_orders(db, portfolio.id)

        await db.commit()
        logger.info("poll_order_fills: %d/%d filled", filled_count, len(orders))
        return {"status": "ok", "filled": filled_count, "checked": len(orders)}


@celery_app.task(name="app.workers.tasks_trading.check_risk_alerts")
def check_risk_alerts():
    """Run risk manager checks on open positions."""
    return run_async(_check_risk_async())


async def _check_risk_async():
    from sqlalchemy import select

    from app.agents.risk_manager import risk_manager_agent
    from app.db.database import get_session_factory
    from app.db.models import Portfolio

    async with get_session_factory()() as db:
        result = await db.execute(select(Portfolio).limit(1))
        portfolio = result.scalar_one_or_none()
        if not portfolio:
            return {"alerts": []}

        alerts = await risk_manager_agent.check_positions(db, portfolio.id)
        await db.commit()
        return {"alerts_count": len(alerts)}
