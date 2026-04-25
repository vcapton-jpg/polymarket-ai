"""CLOB API client — microstructure enrichment (bid/ask/spread/last_trade)."""

import logging
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

CLOB_BASE_URL = "https://clob.polymarket.com"


class ClobClient:
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=CLOB_BASE_URL,
                timeout=15.0,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
    async def get_market(self, condition_id: str) -> Optional[dict]:
        """GET /markets/{condition_id} on CLOB — returns accepting_orders, tokens, etc."""
        client = await self._get_client()
        resp = await client.get(f"/markets/{condition_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    async def enrich_market(self, condition_id: str) -> dict:
        """Fetch CLOB data and return microstructure fields."""
        data = await self.get_market(condition_id)
        if not data:
            return {}

        tokens = data.get("tokens", [])
        best_bid = None
        best_ask = None
        last_trade_price = None

        for token in tokens:
            outcome = (token.get("outcome") or "").upper()
            if outcome == "YES":
                best_bid = _to_float(token.get("price"))
                last_trade_price = best_bid
            elif outcome == "NO":
                best_ask = 1.0 - _to_float(token.get("price", 0))

        spread = None
        if best_bid is not None and best_ask is not None:
            spread = round(best_ask - best_bid, 4)

        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread if spread and spread >= 0 else None,
            "last_trade_price": last_trade_price,
            "accepting_orders": data.get("accepting_orders", True),
        }

    async def get_price_yes(self, condition_id: str) -> Optional[float]:
        """Quick helper: get current YES probability."""
        data = await self.get_market(condition_id)
        if not data:
            return None
        for token in data.get("tokens", []):
            if (token.get("outcome") or "").upper() == "YES":
                return _to_float(token.get("price"))
        return None

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
    async def get_price_24h_ago(self, yes_token_id: str) -> Optional[float]:
        """Fetch the YES price as of ~24h ago from /prices-history.

        Used by the measurement layer to enable `baseline_momentum`. We pull
        the 1-day window (`interval=1d`) and pick the earliest datapoint —
        Polymarket returns a uniform-bucket time series so the first row is
        the oldest sample within the window.

        Returns None if Polymarket has no history yet (brand-new market) or
        the call errors out — the caller treats None as "skip momentum".
        """
        client = await self._get_client()
        try:
            resp = await client.get(
                "/prices-history",
                params={"market": yes_token_id, "interval": "1d"},
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            logger.warning(
                "ClobClient.get_price_24h_ago: token=%s failed: %s", yes_token_id, e,
            )
            return None

        history = data.get("history") or []
        if not history:
            return None
        # First point in `interval=1d` is the oldest (~24h old); newest is
        # the current price. We want the oldest.
        first = history[0]
        return _to_float(first.get("p"))


def _to_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
