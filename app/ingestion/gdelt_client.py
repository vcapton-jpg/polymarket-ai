"""GDELT 2.0 DOC API client — free, no key, 15-min timespan."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class GdeltClient:
    BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
    TIMEOUT_S = 20.0

    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.TIMEOUT_S) as c:
            r = await c.get(self.BASE_URL, params=params)
            r.raise_for_status()
            return r.json()

    async def fetch_recent(
        self,
        query: str,
        timespan: str = "15min",
        max_records: int = 250,
        lang: str = "sourcelang:eng",
    ) -> list[dict[str, Any]]:
        """Return deduped English articles for `query` within `timespan`."""
        params = {
            "query": f"{query} {lang}",
            "mode": "ArtList",
            "maxrecords": max_records,
            "format": "json",
            "timespan": timespan,
            "sort": "DateDesc",
        }
        try:
            data = await self._get(params)
        except httpx.HTTPError as e:
            logger.warning("GDELT fetch failed: %s", e)
            return []

        articles = data.get("articles") or []
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for a in articles:
            url = a.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            out.append(
                {
                    "url": url,
                    "title": a.get("title", "").strip(),
                    "text": "",
                    "source_name": (a.get("domain") or _domain_of(url)).lower(),
                    "publish_date": _parse_seendate(a.get("seendate")),
                    "language": a.get("language", "").lower(),
                }
            )
        return out


def _domain_of(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return (urlparse(url).hostname or "").lower().removeprefix("www.")
    except Exception:
        return ""


def _parse_seendate(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
