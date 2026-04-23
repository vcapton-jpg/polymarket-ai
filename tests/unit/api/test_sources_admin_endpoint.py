"""GET /api/sources returns list of SourceStatsOut with all required fields."""
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app


@pytest.mark.asyncio
async def test_sources_list_endpoint_shape():
    fake_rows = [
        {
            "source_name": "Reuters Top News", "tier": 1, "weight": 0.9,
            "active": True, "source_type": "rss",
            "articles_24h": 12, "signals_contributed_7d": 3,
        },
        {
            "source_name": "Some Blog", "tier": 3, "weight": 0.4,
            "active": True, "source_type": "rss",
            "articles_24h": 0, "signals_contributed_7d": 0,
        },
    ]
    mapping_result = SimpleNamespace(
        mappings=lambda: SimpleNamespace(all=lambda: fake_rows),
    )
    with patch(
        "app.api.routes.sources.AsyncSession.execute",
        new=AsyncMock(return_value=mapping_result),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.get("/api/sources")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 2
    for row in data:
        for k in ("source_name", "tier", "weight", "active", "source_type",
                  "articles_24h", "signals_contributed_7d"):
            assert k in row
    assert data[0]["source_name"] == "Reuters Top News"
