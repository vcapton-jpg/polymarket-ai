"""Polymarket Builder API client — trade execution via CLOB."""

import logging
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)

CLOB_HOST = "https://clob.polymarket.com"


class BuilderTradeClient:
    """Wraps py-clob-client with Builder credentials for order execution."""

    def __init__(self):
        self._client = None
        self._settings = get_settings()

    def _get_client(self):
        if self._client is not None:
            return self._client

        s = self._settings
        if not s.builder_private_key:
            raise RuntimeError("BUILDER_PRIVATE_KEY not configured")

        try:
            from py_clob_client.client import ClobClient
        except ImportError:
            raise RuntimeError("py-clob-client not installed: pip install py-clob-client")

        creds = None
        if s.builder_api_key and s.builder_api_secret and s.builder_api_passphrase:
            from py_clob_client.clob_types import ApiCreds
            creds = ApiCreds(
                api_key=s.builder_api_key,
                api_secret=s.builder_api_secret,
                api_passphrase=s.builder_api_passphrase,
            )

        self._client = ClobClient(
            host=CLOB_HOST,
            chain_id=s.polygon_chain_id,
            key=s.builder_private_key,
            creds=creds,
        )

        if creds is None:
            derived = self._client.create_or_derive_api_creds()
            self._client.set_api_creds(derived)
            logger.info("Derived CLOB API creds for builder wallet")

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
            price: Limit price (0-1).
            size: Number of shares.
        """
        from py_clob_client.clob_types import OrderType
        client = self._get_client()

        order_args = {
            "token_id": token_id,
            "price": price,
            "size": size,
            "side": side.upper(),
        }
        options = {"tick_size": tick_size, "neg_risk": neg_risk}

        try:
            resp = client.create_and_post_order(order_args, options, OrderType.GTC)
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
        """Place a FOK market order."""
        from py_clob_client.clob_types import OrderType
        client = self._get_client()

        order_args = {
            "token_id": token_id,
            "amount": amount,
            "side": side.upper(),
        }
        options = {"tick_size": tick_size, "neg_risk": neg_risk}

        try:
            resp = client.create_and_post_market_order(order_args, options, OrderType.FOK)
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

    async def cancel_order(self, order_id: str) -> dict:
        client = self._get_client()
        try:
            resp = client.cancel(order_id)
            return {"success": True, "data": resp}
        except Exception as e:
            logger.error("Cancel failed: %s", e, exc_info=True)
            return {"success": False, "error": str(e)}

    async def get_open_orders(self, market_id: Optional[str] = None) -> list:
        client = self._get_client()
        try:
            params = {}
            if market_id:
                params["market"] = market_id
            return client.get_open_orders(params) or []
        except Exception as e:
            logger.error("get_open_orders failed: %s", e, exc_info=True)
            return []

    async def get_price_yes(self, condition_id: str) -> Optional[float]:
        client = self._get_client()
        try:
            data = client.get_market(condition_id)
            if not data:
                return None
            for token in data.get("tokens", []):
                if (token.get("outcome") or "").upper() == "YES":
                    return float(token.get("price", 0))
        except Exception:
            pass
        return None


_instance: Optional[BuilderTradeClient] = None


def get_trade_client() -> BuilderTradeClient:
    global _instance
    if _instance is None:
        _instance = BuilderTradeClient()
    return _instance
