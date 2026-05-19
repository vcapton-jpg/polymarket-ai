"""Gamma API client — fetch all active markets via the events endpoint."""

import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
PAGE_SIZE = 100


class GammaClient:
    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=GAMMA_BASE_URL,
                timeout=30.0,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def _get(self, path: str, params: dict) -> list | dict:
        client = await self._get_client()
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def fetch_all_active_markets(self) -> list[dict]:
        """Paginate through /events?active=true&closed=false and flatten markets."""
        all_markets: list[dict] = []
        offset = 0

        while True:
            data = await self._get("/events", params={
                "active": "true",
                "closed": "false",
                "limit": PAGE_SIZE,
                "offset": offset,
            })

            events = data if isinstance(data, list) else data.get("data", [])
            if not events:
                break

            for event in events:
                raw_markets = event.get("markets", [])
                for m in raw_markets:
                    parsed = self._parse_market(m, event)
                    if parsed:
                        all_markets.append(parsed)

            if len(events) < PAGE_SIZE:
                break
            offset += PAGE_SIZE

        logger.info("Gamma: fetched %d active markets", len(all_markets))
        return all_markets

    @staticmethod
    def _parse_market(m: dict, event: dict) -> dict | None:
        condition_id = m.get("conditionId")
        question = m.get("question") or m.get("groupItemTitle")
        if not condition_id or not question:
            return None

        tokens = m.get("clobTokenIds") or m.get("clob_token_ids")
        clob_token_ids = None
        if isinstance(tokens, list) and len(tokens) >= 2:
            clob_token_ids = {"yes": tokens[0], "no": tokens[1]}
        elif isinstance(tokens, dict):
            clob_token_ids = tokens

        tags_raw = event.get("tags") or m.get("tags")
        tags = None
        if isinstance(tags_raw, list):
            tags = [t.get("label") if isinstance(t, dict) else str(t) for t in tags_raw]
        elif isinstance(tags_raw, str):
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

        # Gamma exposes both market-level (`image`/`icon`) and event-level
        # imagery. Market-level art is more specific (e.g. a candidate's photo
        # in a multi-outcome election event), so prefer it; fall back to the
        # event icon for binary markets where the market itself has no image.
        image_url = (
            m.get("image")
            or m.get("icon")
            or event.get("image")
            or event.get("icon")
        )

        # Polymarket web pages live at /event/<event-slug> (200). The
        # event slug is the canonical, always-resolvable deep link;
        # market slug is a fallback. NEVER build /market/<conditionId>
        # — it 307s to /404 (the "broken links" bug, fixed 2026-05-19).
        slug = event.get("slug") or m.get("slug")

        return {
            "market_id": condition_id,
            "slug": slug,
            "question": question,
            "description": (m.get("description") or event.get("description") or "")[:2000],
            "category": event.get("category") or (tags[0] if tags else None),
            "tags": tags,
            "end_date": m.get("endDate") or event.get("endDate"),
            "active": m.get("active", True),
            "closed": m.get("closed", False),
            "accepting_orders": m.get("acceptingOrders", True),
            "volume": _to_float(m.get("volume")),
            "volume_24h": _to_float(m.get("volume24hr")),
            "liquidity": _to_float(m.get("liquidity")),
            "last_trade_price": _to_float(m.get("lastTradePrice")),
            "clob_token_ids": clob_token_ids,
            "image_url": image_url,
        }


def _to_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
