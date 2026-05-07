"""Trading API routes — order placement, portfolio, positions."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.routes.auth import get_current_user
from app.db.database import get_db_session
from app.db.models import Market, Order, Portfolio, Position, UserProfile
from app.services.user_limits import can_trade_real, register_trade_opened

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/trading", tags=["trading"])


# Per-trade upper bound (USDC). Hard cap rather than a soft `can_trade_real`
# check because Pydantic short-circuits before any business logic runs — any
# `amount` outside this range never reaches `can_trade_real`, the CLOB
# client, or a Safe transaction. Audit follow-up 2026-05-05.
TRADE_AMOUNT_MAX_USDC = 10_000.0


class TradeRequest(BaseModel):
    market_id: str = Field(min_length=1, max_length=128)
    direction: str  # BUY_YES or BUY_NO — validated in handler
    # Strict bounds: zero/negative blocked at the schema layer before the
    # handler runs. The previous `amount: float` accepted anything Python
    # could parse — including `-100`, `0`, `1e9`, NaN — and depended on
    # downstream code (`can_trade_real`, the CLOB client) to bounce it.
    # That defense-in-depth layer is real but should never be the first
    # validator a hostile request meets.
    amount: float = Field(gt=0, le=TRADE_AMOUNT_MAX_USDC)
    # Polymarket prices are probabilities ∈ (0, 1); accept the inclusive
    # 1-cent margin Polymarket itself enforces. None still means "market
    # order" downstream.
    price: float | None = Field(default=None, ge=0.01, le=0.99)
    signal_id: int | None = Field(default=None, ge=1)


class TradeResponse(BaseModel):
    success: bool
    order_id: int | None = None
    polymarket_order_id: str | None = None
    error: str | None = None


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    market_id: str
    side: str
    size: float
    entry_price: float
    current_price: float | None = None
    pnl_pct: float | None = None
    status: str
    market_question: str | None = None


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    market_id: str
    side: str
    price: float
    size: float
    order_type: str
    status: str
    polymarket_order_id: str | None = None
    error_msg: str | None = None
    created_at: str
    filled_at: str | None = None


class PortfolioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    total_value: float
    cash_balance: float
    positions: list[PositionOut]
    open_orders_count: int


async def _get_or_create_portfolio(
    db: AsyncSession, user: UserProfile,
) -> Portfolio:
    """Get the calling user's portfolio, creating it lazily if absent.

    Filters on `user_id` so the cross-user leak fixed in PR #13 (P0-2)
    cannot regress. The pre-fix version of this function also created
    a ghost `UserProfile(plan="free")` row each time it was hit; those
    orphans were swept by Alembic 026 (P1-3, 2026-04-27) and the
    `user_profiles.email` column is now NOT NULL so the schema itself
    forbids that pattern from ever recurring.
    """
    result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == user.id).limit(1)
    )
    portfolio = result.scalar_one_or_none()
    if portfolio:
        return portfolio

    portfolio = Portfolio(
        user_id=user.id, name="Main", total_value=0, cash_balance=0,
    )
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
    # Pivot 2026-04-23: gate real-money trading on UserLimits
    # (age/quiz/budget/cooloff/onboarding). Runs BEFORE the wallet
    # check so unmet-limit users are rejected consistently regardless
    # of wallet state.
    decision = await can_trade_real(user_id=user.id, stake_eur=float(req.amount))
    if not decision.allowed:
        raise HTTPException(status_code=403, detail={"reason": decision.reason})

    if not user.polymarket_safe_address:
        return TradeResponse(success=False, error="wallet_not_connected")

    portfolio = await _get_or_create_portfolio(db, user)

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

    # Debit the user's weekly budget after the order is persisted.
    # register_trade_opened() manages its own session, so running it
    # post-commit keeps the two writes decoupled. Trade-off: if this
    # call fails the order is already persisted — acceptable because
    # (a) can_trade_real already validated the budget, so we know the
    # debit is within bounds; (b) this counter feeds client-side UX,
    # not authoritative enforcement (which happens in can_trade_real
    # on the next attempt).
    if order.status == "submitted":
        await register_trade_opened(user_id=user.id, stake_eur=float(req.amount))

    return TradeResponse(
        success=order.status == "submitted",
        order_id=order.id,
        polymarket_order_id=order.polymarket_order_id,
        error=order.error_msg,
    )


@router.get("/portfolio", response_model=PortfolioOut)
async def get_portfolio(
    db: AsyncSession = Depends(get_db_session),
    user: UserProfile = Depends(get_current_user),
):
    """Get the calling user's portfolio with their positions."""
    result = await db.execute(
        select(Portfolio)
        .where(Portfolio.user_id == user.id)
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


class ClobMarketInfo(BaseModel):
    """Minimal CLOB info the frontend needs to build a Polymarket order.

    Returned to the OrderForm before it asks the user's MetaMask for an
    EIP-712 signature, so the frontend can pick the right token_id
    (YES vs NO) and the correct tick_size for the market.
    """
    market_id: str
    yes_token_id: str | None
    no_token_id: str | None
    tick_size: str = "0.01"
    neg_risk: bool = False
    last_trade_price: float | None = None
    accepting_orders: bool = True


@router.get("/markets/{market_id}/clob-info", response_model=ClobMarketInfo)
async def get_clob_market_info(
    market_id: str,
    db: AsyncSession = Depends(get_db_session),
    user: UserProfile = Depends(get_current_user),
) -> ClobMarketInfo:
    """Resolve the CLOB token_ids + trading params for `market_id`.

    The non-custodial trading flow (Polymarket Builder pattern) requires
    the frontend to know the YES/NO token_id before it can build an
    OrderArgs for clob-client. Rather than expose `clob_token_ids` on
    every signal payload (bloats list responses), the OrderForm calls
    this endpoint once when the user opens the order panel.

    JWT-protected — only authed users see token_ids; the public catalog
    only ever returns the human-readable `polymarketUrl`.

    `tick_size` and `neg_risk` are not yet columns on our Market table
    (we never needed them server-side because the old custodial path
    used py-clob-client defaults). They default here to the safe
    Polymarket fallback (`tick_size="0.01"`, `neg_risk=False`) which
    holds for ~99 % of binary markets.
    """
    result = await db.execute(select(Market).where(Market.market_id == market_id))
    market = result.scalar_one_or_none()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    token_ids = market.clob_token_ids or {}
    yes_token = token_ids.get("yes") or token_ids.get("YES")
    no_token = token_ids.get("no") or token_ids.get("NO")

    return ClobMarketInfo(
        market_id=market.market_id,
        yes_token_id=yes_token,
        no_token_id=no_token,
        tick_size="0.01",
        neg_risk=False,
        last_trade_price=float(market.last_trade_price) if market.last_trade_price else None,
        accepting_orders=bool(market.accepting_orders),
    )


class OrderRecordRequest(BaseModel):
    """Frontend-placed order to persist for portfolio tracking.

    The non-custodial flow has the user's MetaMask sign the order and
    the browser's clob-client POSTs it directly to clob.polymarket.com
    (with our /api/polymarket/sign HMAC for builder attribution). After
    a successful submit we ping THIS endpoint so the order shows up in
    the user's portfolio, the worker fill-poller picks it up, and the
    risk-manager can monitor it.

    Crucial: the FRONTEND has already executed the trade by the time
    this endpoint is called. We are NOT placing the order here — that
    would require a server-side private key (the rejected custodial
    pattern). We are only RECORDING something the user already did.
    """
    market_id: str = Field(min_length=1, max_length=128)
    polymarket_order_id: str = Field(min_length=1, max_length=128)
    direction: str = Field(pattern=r"^(YES|NO|BUY_YES|BUY_NO)$")
    token_id: str = Field(min_length=1, max_length=128)
    size: float = Field(gt=0, le=TRADE_AMOUNT_MAX_USDC)
    price: float = Field(gt=0, lt=1)
    order_type: str = Field(default="GTC", pattern=r"^(GTC|FOK|GTD|FAK)$")
    signal_id: int | None = Field(default=None, ge=1)


class OrderRecordResponse(BaseModel):
    success: bool
    order_id: int | None = None
    error: str | None = None


@router.post("/orders/record", response_model=OrderRecordResponse)
async def record_order(
    req: OrderRecordRequest,
    db: AsyncSession = Depends(get_db_session),
    user: UserProfile = Depends(get_current_user),
) -> OrderRecordResponse:
    """Persist a frontend-placed order so the portfolio + workers see it.

    This is the non-custodial counterpart to `/trade`. The contract:
      - Frontend has already received `polymarket_order_id` from the
        Polymarket CLOB (the user signed in MetaMask, the order is
        accepted by Polymarket).
      - We only persist metadata. We do NOT call back to Polymarket
        to verify — the worker `poll_order_fills` task will reconcile
        on its next pass (every 60 s) and update the status.

    Limit gating mirrors `/trade`: `can_trade_real` for age + cooloff,
    plus the same TRADE_AMOUNT_MAX_USDC cap on size. We also debit the
    weekly budget tracker on success so the trade-cap UX stays honest.
    """
    decision = await can_trade_real(user_id=user.id, stake_eur=float(req.size))
    if not decision.allowed:
        raise HTTPException(status_code=403, detail={"reason": decision.reason})

    if not user.polymarket_safe_address:
        return OrderRecordResponse(
            success=False, error="wallet_not_connected"
        )

    portfolio = await _get_or_create_portfolio(db, user)

    # Sanity check the market exists in our table — guards against the
    # frontend sending a stale or fabricated market_id.
    market_exists = await db.execute(
        select(Market.market_id).where(Market.market_id == req.market_id)
    )
    if market_exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Market not found")

    # Guard against duplicate `polymarket_order_id` if the frontend
    # double-fires the record call. Idempotent: return the existing row.
    existing = await db.execute(
        select(Order).where(
            Order.portfolio_id == portfolio.id,
            Order.polymarket_order_id == req.polymarket_order_id,
        )
    )
    duplicate = existing.scalar_one_or_none()
    if duplicate is not None:
        return OrderRecordResponse(success=True, order_id=duplicate.id)

    side = "BUY"  # The Builder flow always passes BUY-side orders
                  # (BUY_YES = buy YES token, BUY_NO = buy NO token).
                  # SELL-side closes are routed via a separate flow.

    order = Order(
        portfolio_id=portfolio.id,
        market_id=req.market_id,
        signal_id=req.signal_id,
        token_id=req.token_id,
        side=side,
        price=req.price,
        size=req.size,
        order_type=req.order_type,
        polymarket_order_id=req.polymarket_order_id,
        # `submitted` not `pending` — the frontend already put it on the
        # CLOB. The worker poll will flip it to `filled` (or `cancelled`
        # / `failed`) on the next sweep.
        status="submitted",
    )
    db.add(order)
    await db.flush()
    await db.commit()

    # Debit the weekly budget tracker (same as /trade post-commit).
    await register_trade_opened(user_id=user.id, stake_eur=float(req.size))

    logger.info(
        "Order recorded: user=%s portfolio=%s market=%s polymarket_id=%s size=%s",
        user.id, portfolio.id, req.market_id, req.polymarket_order_id, req.size,
    )

    return OrderRecordResponse(success=True, order_id=order.id)


@router.get("/orders")
async def get_orders(
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db_session),
    user: UserProfile = Depends(get_current_user),
):
    """Get the calling user's order history."""
    result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == user.id).limit(1)
    )
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
