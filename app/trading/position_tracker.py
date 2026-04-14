"""Position tracker — syncs portfolio state from orders and market prices."""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Order, Position, Portfolio

logger = logging.getLogger(__name__)


async def sync_positions_from_orders(db: AsyncSession, portfolio_id: int) -> int:
    """Create/update positions based on filled orders. Returns count of positions updated."""
    filled_orders = await db.execute(
        select(Order)
        .where(Order.portfolio_id == portfolio_id, Order.status == "filled")
        .order_by(Order.filled_at)
    )
    orders = filled_orders.scalars().all()

    positions_map: dict[str, Position] = {}
    existing = await db.execute(
        select(Position).where(Position.portfolio_id == portfolio_id, Position.status == "open")
    )
    for pos in existing.scalars().all():
        positions_map[f"{pos.market_id}:{pos.side}"] = pos

    updated = 0
    for order in orders:
        key = f"{order.market_id}:{order.side}"
        if key not in positions_map:
            pos = Position(
                portfolio_id=portfolio_id,
                market_id=order.market_id,
                token_id=order.token_id,
                side=order.side,
                size=float(order.filled_size or order.size),
                entry_price=float(order.filled_price or order.price),
                current_price=float(order.filled_price or order.price),
                pnl_pct=0.0,
                status="open",
            )
            db.add(pos)
            positions_map[key] = pos
            updated += 1
        else:
            pos = positions_map[key]
            added_size = float(order.filled_size or order.size)
            old_cost = pos.size * pos.entry_price
            new_cost = added_size * float(order.filled_price or order.price)
            pos.size += added_size
            pos.entry_price = (old_cost + new_cost) / pos.size if pos.size > 0 else 0
            updated += 1

    await db.flush()
    return updated


async def update_position_prices(
    db: AsyncSession, portfolio_id: int, prices: dict[str, float]
) -> int:
    """Update current_price and pnl_pct for open positions."""
    result = await db.execute(
        select(Position).where(Position.portfolio_id == portfolio_id, Position.status == "open")
    )
    positions = result.scalars().all()
    updated = 0
    for pos in positions:
        if pos.market_id in prices:
            pos.current_price = prices[pos.market_id]
            if pos.entry_price and pos.entry_price > 0:
                if pos.side == "BUY":
                    pos.pnl_pct = ((pos.current_price - pos.entry_price) / pos.entry_price) * 100
                else:
                    pos.pnl_pct = ((pos.entry_price - pos.current_price) / pos.entry_price) * 100
            updated += 1
    await db.flush()
    return updated
