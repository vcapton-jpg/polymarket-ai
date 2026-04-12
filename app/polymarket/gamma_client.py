"""Gamma API client for Polymarket markets."""

import json
import logging
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Gamma API base URL
GAMMA_BASE_URL = "https://gamma-api.polymarket.com"


class GammaClient:
    """Client for Polymarket Gamma API."""

    def __init__(self):
        """Initialize the Gamma client."""
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

    async def fetch_markets(self, limit: int = 100) -> list[dict]:
        """Fetch active markets.

        Args:
            limit: Maximum number of markets.

        Returns:
            List of market dictionaries.
        """
        markets = []

        try:
            session = await self._get_session()

            response = await session.get(
                f"{GAMMA_BASE_URL}/markets",
                params={"closed": False, "limit": limit},
            )

            if response.status_code == 200:
                data = response.json()
                markets_raw = data.get("data", []) if isinstance(data, dict) else data

                for market in markets_raw:
                    markets.append(
                        {
                            "market_id": market.get("conditionId"),
                            "question": market.get("question"),
                            "description": market.get("description"),
                            "groupItemId": market.get("groupItemId"),
                            "volume": market.get("volume"),
                            "volume24hr": market.get("volume24hr"),
                            "liquidity": market.get("liquidity"),
                            "active": market.get("active"),
                            "closed": market.get("closed"),
                            "endDate": market.get("endDate"),
                            "createdAt": market.get("createdAt"),
                        }
                    )

        except Exception as e:
            logger.error(f"Error fetching markets: {e}")

        return markets

    async def fetch_market_by_id(self, market_id: str) -> Optional[dict]:
        """Fetch a specific market.

        Args:
            market_id: Market ID.

        Returns:
            Market dictionary or None.
        """
        try:
            session = await self._get_session()

            response = await session.get(f"{GAMMA_BASE_URL}/markets/{market_id}")

            if response.status_code == 200:
                return response.json()

        except Exception as e:
            logger.error(f"Error fetching market {market_id}: {e}")

        return None


def create_gamma_client() -> GammaClient:
    """Create a Gamma client.

    Returns:
        Configured GammaClient.
    """
    return GammaClient()