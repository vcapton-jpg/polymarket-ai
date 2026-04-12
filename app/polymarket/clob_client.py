"""CLob client for real-time market prices."""

import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# CLob API base URL
CLOB_BASE_URL = "https://clob-api.polymarket.com"


class ClobClient:
    """Client for Polymarket CLOB API."""

    def __init__(self):
        """Initialize the CLOB client."""
        self._session: Optional[httpx.AsyncClient] = None

    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session."""
        if self._session is None or self._session.is_closed:
            self._session = httpx.AsyncClient(timeout=30.0)
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.is_closed:
            await self._session.aclose()

    async def get_order_book(
        self,
        market_id: str,
    ) -> Optional[dict]:
        """Get order book for a market.

        Args:
            market_id: Market ID.

        Returns:
            Order book dictionary.
        """
        try:
            session = await self._get_session()

            response = await session.get(
                f"{CLOB_BASE_URL}/orderbooks/{market_id}",
            )

            if response.status_code == 200:
                return response.json()

        except Exception as e:
            logger.error(f"Error fetching order book: {e}")

        return None

    async def get_best_prices(
        self,
        market_id: str,
    ) -> Optional[dict]:
        """Get best bid and ask for a market.

        Args:
            market_id: Market ID.

        Returns:
            Dictionary with best_bid, best_ask, spread.
        """
        order_book = await self.get_order_book(market_id)

        if not order_book:
            return None

        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])

        best_bid = float(bids[0]["price"]) if bids else None
        best_ask = float(asks[0]["price"]) if asks else None

        spread = None
        if best_bid and best_ask:
            spread = best_ask - best_bid

        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
        }

    async def get_price(self, market_id: str, side: str = "YES") -> Optional[float]:
        """Get price for a side.

        Args:
            market_id: Market ID.
            side: "YES" or "NO".

        Returns:
            Price or None.
        """
        order_book = await self.get_order_book(market_id)

        if not order_book:
            return None

        if side == "YES":
            prices = order_book.get("bids", [])
        else:
            prices = order_book.get("asks", [])

        return float(prices[0]["price"]) if prices else None


def create_clob_client() -> ClobClient:
    """Create a CLOB client.

    Returns:
        Configured ClobClient.
    """
    return ClobClient()