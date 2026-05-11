"""Polymarket Builder API client — trade execution via CLOB (py-clob-client-v2)."""

import asyncio
import logging

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import (
    ApiCreds,
    MarketOrderArgsV2,
    OrderArgsV2,
    OrderPayload,
    OrderType,
    PartialCreateOrderOptions,
)
from py_clob_client_v2.order_utils.model.side import Side

from app.core.config import get_settings

logger = logging.getLogger(__name__)

CLOB_HOST = "https://clob.polymarket.com"


def get_user_clob_client(safe_address: str) -> ClobClient:
    """Create a ClobClient for a specific Gnosis Safe (funder pattern).

    Args:
        safe_address: The user's Gnosis Safe address — used as the ``funder``
                      so that orders are settled from that Safe's USDC balance.

    Returns:
        A fully initialised :class:`~py_clob_client_v2.client.ClobClient`.
    """
    s = get_settings()

    if not s.builder_private_key:
        raise RuntimeError("BUILDER_PRIVATE_KEY not configured")

    creds: ApiCreds | None = None
    if s.builder_api_key and s.builder_api_secret and s.builder_api_passphrase:
        creds = ApiCreds(
            api_key=s.builder_api_key,
            api_secret=s.builder_api_secret,
            api_passphrase=s.builder_api_passphrase,
        )

    client = ClobClient(
        host=CLOB_HOST,
        chain_id=s.polygon_chain_id,
        key=s.builder_private_key,
        creds=creds,
        funder=safe_address,
    )

    if creds is None:
        derived = client.create_or_derive_api_key()
        client.set_api_creds(derived)
        logger.info("Derived CLOB API creds for builder wallet (funder=%s)", safe_address)

    return client


class BuilderTradeClient:
    """Async wrapper around :class:`~py_clob_client_v2.client.ClobClient`.

    Uses the ``funder`` pattern so that every order is settled from the user's
    Gnosis Safe rather than the builder wallet directly.
    """

    def __init__(self, safe_address: str):
        self._safe_address = safe_address
        self._client: ClobClient | None = None
        self._settings = get_settings()

    def _get_client(self) -> ClobClient:
        if self._client is None:
            self._client = get_user_clob_client(self._safe_address)
        return self._client

    async def place_limit_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
        tick_size: str = "0.01",
        neg_risk: bool = False,
    ) -> dict:
        """Place a GTC limit order.

        Args:
            token_id: The outcome token ID.
            side: 'BUY' or 'SELL'.
            price: Limit price (0–1).
            size: Number of shares.
            tick_size: Price granularity ('0.1', '0.01', '0.001', '0.0001').
            neg_risk: Whether this is a neg-risk market.
        """
        if not self._safe_address:
            raise ValueError("Cannot place orders without a user Safe address")
        client = self._get_client()

        order_args = OrderArgsV2(
            token_id=token_id,
            price=price,
            size=size,
            side=Side.BUY if side.upper() == "BUY" else Side.SELL,
            builder_code=self._settings.polymarket_builder_code,
        )
        options = PartialCreateOrderOptions(tick_size=tick_size, neg_risk=neg_risk)

        try:
            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(None, lambda: client.create_and_post_order(order_args, options, OrderType.GTC))
            logger.info(
                "Order placed: side=%s price=%.4f size=%.1f token=%s… → %s",
                side, price, size, token_id[:16], resp.get("orderID", "?"),
            )
            return {
                "success": resp.get("success", False),
                "order_id": resp.get("orderID"),
                "error": resp.get("errorMsg"),
            }
        except Exception as e:
            logger.error("Order failed: %s", e, exc_info=True)
            return {"success": False, "order_id": None, "error": str(e)}

    async def place_market_order(
        self,
        token_id: str,
        side: str,
        amount: float,
        tick_size: str = "0.01",
        neg_risk: bool = False,
    ) -> dict:
        """Place a FOK market order.

        Args:
            token_id: The outcome token ID.
            side: 'BUY' or 'SELL'.
            amount: USDC amount to spend.
            tick_size: Price granularity.
            neg_risk: Whether this is a neg-risk market.
        """
        if not self._safe_address:
            raise ValueError("Cannot place orders without a user Safe address")
        client = self._get_client()

        order_args = MarketOrderArgsV2(
            token_id=token_id,
            amount=amount,
            side=Side.BUY if side.upper() == "BUY" else Side.SELL,
            builder_code=self._settings.polymarket_builder_code,
        )
        options = PartialCreateOrderOptions(tick_size=tick_size, neg_risk=neg_risk)

        try:
            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(None, lambda: client.create_and_post_market_order(order_args, options, OrderType.FOK))
            logger.info(
                "Market order: side=%s amount=%.2f token=%s… → %s",
                side, amount, token_id[:16], resp.get("orderID", "?"),
            )
            return {
                "success": resp.get("success", False),
                "order_id": resp.get("orderID"),
                "error": resp.get("errorMsg"),
            }
        except Exception as e:
            logger.error("Market order failed: %s", e, exc_info=True)
            return {"success": False, "order_id": None, "error": str(e)}

    async def get_order(self, order_id: str) -> dict | None:
        """Fetch a single order by ID."""
        client = self._get_client()
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: client.get_order(order_id))
        except Exception as e:
            logger.error("get_order failed: %s", e, exc_info=True)
            return None

    async def cancel_order(self, order_id: str) -> dict:
        """Cancel an open order by ID."""
        client = self._get_client()
        try:
            payload = OrderPayload(orderID=order_id)
            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(None, lambda: client.cancel_order(payload))
            return {"success": True, "data": resp}
        except Exception as e:
            logger.error("Cancel failed: %s", e, exc_info=True)
            return {"success": False, "error": str(e)}

    async def get_open_orders(self, market_id: str | None = None) -> list:
        """Return all open orders, optionally filtered by market."""
        client = self._get_client()
        try:
            params = {}
            if market_id:
                params["market"] = market_id
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: client.get_open_orders(params)) or []
        except Exception as e:
            logger.error("get_open_orders failed: %s", e, exc_info=True)
            return []

    async def get_price_yes(self, condition_id: str) -> float | None:
        """Return the current YES price for a market."""
        client = self._get_client()
        try:
            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(None, lambda: client.get_market(condition_id))
            if not data:
                return None
            for token in data.get("tokens", []):
                if (token.get("outcome") or "").upper() == "YES":
                    return float(token.get("price", 0))
        except Exception:
            pass
        return None


