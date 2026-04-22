"""Trading API routes — order placement, portfolio, positions."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.routes.auth import get_current_user
from app.db.database import get_db_session
from app.db.models import Market, Order, Portfolio, Position, UserProfile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/trading", tags=["trading"])


class TradeRequest(BaseModel):
    market_id: str
    direction: str  # BUY_YES or BUY_NO
    amount: float
    price: Optional[float] = None  # None = market order
    signal_id: Optional[int] = None


class TradeResponse(BaseModel):
    success: bool
    order_id: Optional[int] = None
    polymarket_order_id: Optional[str] = None
    error: Optional[str] = None


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    market_id: str
    side: str
    size: float
    entry_price: float
    current_price: Optional[float] = None
    pnl_pct: Optional[float] = None
    status: str
    market_question: Optional[str] = None


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    market_id: str
    side: str
    price: float
    size: float
    order_type: str
    status: str
    polymarket_order_id: Optional[str] = None
    error_msg: Optional[str] = None
    created_at: str
    filled_at: Optional[str] = None


class PortfolioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    total_value: float
    cash_balance: float
    positions: list[PositionOut]
    open_orders_count: int


async def _get_or_create_portfolio(db: AsyncSession) -> Portfolio:
    """Get the default portfolio, creating user + portfolio if needed."""
    result = await db.execute(select(Portfolio).limit(1))
    portfolio = result.scalar_one_or_none()
    if portfolio:
        return portfolio

    user = UserProfile(plan="free")
    db.add(user)
    await db.flush()

    portfolio = Portfolio(user_id=user.id, name="Main", total_value=0, cash_balance=0)
    db.add(portfolio)
    await db.flush()
    return portfolio


@router.post("/trade", response_model=TradeResponse)
async def place_trade(
    req: TradeRequest,
    db: AsyncSession = Depends(get_db_session),
    user: UserProfile = Depends(get_current_user),
):
    """Place a trade on Polymarket."""
    if not user.polymarket_safe_address:
        return TradeResponse(success=False, error="wallet_not_connected")

    portfolio = await _get_or_create_portfolio(db)

    market_result = await db.execute(select(Market).where(Market.market_id == req.market_id))
    market = market_result.scalar_one_or_none()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    if not market.clob_token_ids:
        raise HTTPException(status_code=400, detail="Market has no token IDs for trading")

    token_ids = market.clob_token_ids
    if req.direction == "BUY_YES":
        token_id = token_ids.get("yes") or token_ids.get("YES")
        side = "BUY"
    elif req.direction == "BUY_NO":
        token_id = token_ids.get("no") or token_ids.get("NO")
        side = "BUY"
    else:
        raise HTTPException(status_code=400, detail="direction must be BUY_YES or BUY_NO")

    if not token_id:
        raise HTTPException(status_code=400, detail="Could not resolve token ID for direction")

    price = req.price or float(market.last_trade_price or 0.5)
    order = Order(
        portfolio_id=portfolio.id,
        market_id=req.market_id,
        signal_id=req.signal_id,
        token_id=token_id,
        side=side,
        price=price,
        size=req.amount,
        order_type="GTC" if req.price else "FOK",
        status="pending",
    )
    db.add(order)
    await db.flush()

    from app.trading.builder_client import BuilderTradeClient
    client = BuilderTradeClient(user.polymarket_safe_address)

    try:
        if req.price:
            resp = await client.place_limit_order(
                token_id=token_id, side=side, price=price, size=req.amount,
            )
        else:
            resp = await client.place_market_order(
                token_id=token_id, side=side, amount=req.amount,
            )

        if resp.get("success"):
            order.polymarket_order_id = resp.get("order_id")
            order.status = "submitted"
        else:
            order.status = "failed"
            order.error_msg = resp.get("error", "Unknown error")

    except Exception as e:
        order.status = "failed"
        order.error_msg = str(e)

    await db.commit()

    return TradeResponse(
        success=order.status == "submitted",
        order_id=order.id,
        polymarket_order_id=order.polymarket_order_id,
        error=order.error_msg,
    )


@router.get("/portfolio", response_model=PortfolioOut)
async def get_portfolio(db: AsyncSession = Depends(get_db_session)):
    """Get the current portfolio with positions."""
    result = await db.execute(
        select(Portfolio)
        .options(selectinload(Portfolio.positions).selectinload(Position.market))
        .limit(1)
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="No portfolio found")

    open_orders = await db.execute(
        select(Order)
        .where(Order.portfolio_id == portfolio.id, Order.status.in_(["pending", "submitted"]))
    )
    open_count = len(open_orders.scalars().all())

    positions_out = []
    for pos in portfolio.positions:
        positions_out.append(PositionOut(
            id=pos.id,
            market_id=pos.market_id,
            side=pos.side,
            size=float(pos.size),
            entry_price=float(pos.entry_price),
            current_price=float(pos.current_price) if pos.current_price else None,
            pnl_pct=float(pos.pnl_pct) if pos.pnl_pct else None,
            status=pos.status,
            market_question=pos.market.question if pos.market else None,
        ))

    return PortfolioOut(
        id=portfolio.id,
        name=portfolio.name,
        total_value=float(portfolio.total_value),
        cash_balance=float(portfolio.cash_balance),
        positions=positions_out,
        open_orders_count=open_count,
    )


@router.get("/orders")
async def get_orders(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db_session),
):
    """Get order history."""
    result = await db.execute(select(Portfolio).limit(1))
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        return {"orders": [], "total": 0}

    query = select(Order).where(Order.portfolio_id == portfolio.id)
    if status:
        query = query.where(Order.status == status)
    query = query.order_by(desc(Order.created_at)).limit(limit)

    result = await db.execute(query)
    orders = result.scalars().all()

    return {
        "orders": [
            {
                "id": o.id,
                "market_id": o.market_id,
                "side": o.side,
                "price": float(o.price),
                "size": float(o.size),
                "order_type": o.order_type,
                "status": o.status,
                "polymarket_order_id": o.polymarket_order_id,
                "error_msg": o.error_msg,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "filled_at": o.filled_at.isoformat() if o.filled_at else None,
            }
            for o in orders
        ],
        "total": len(orders),
    }
