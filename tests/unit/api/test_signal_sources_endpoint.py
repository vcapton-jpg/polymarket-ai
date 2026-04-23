"""GET /api/signals/{id}/sources — returns relevance-sorted list via build_detailed_sources."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app


def _make_signal_with_links():
    t = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    def mk(news_id, rel):
        news = SimpleNamespace(
            id=news_id, title=f"t{news_id}", url=f"https://e/{news_id}",
            source_name="Reuters Top News", source_tier=1,
            source_weight=0.9, publish_date=t,
        )
        return SimpleNamespace(
            news_clean=SimpleNamespace(news=news),
            key_excerpt="exc",
            relevance_score=rel,
        )
    event = SimpleNamespace(news_links=[mk(1, 0.3), mk(2, 0.9), mk(3, 0.6)])
    return SimpleNamespace(id=42, event_id=7, event=event)


@pytest.mark.asyncio
async def test_signal_sources_returns_sorted_list():
    signal = _make_signal_with_links()

    with patch(
        "app.api.routes.AsyncSession.execute",
        new=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: signal)),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.get("/api/signals/42/sources")
    assert r.status_code == 200
    data = r.json()
    assert [d["newsId"] for d in data] == [2, 3, 1]
    assert data[0]["role"] == "primary"
    assert data[1]["role"] == "supporting"


@pytest.mark.asyncio
async def test_signal_sources_404_when_missing():
    with patch(
        "app.api.routes.AsyncSession.execute",
        new=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.get("/api/signals/99999/sources")
    assert r.status_code == 404
