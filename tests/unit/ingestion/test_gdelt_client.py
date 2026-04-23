"""GDELT client — payload parsing and dedupe."""
from unittest.mock import AsyncMock, patch

import pytest

from app.ingestion.gdelt_client import GdeltClient


SAMPLE_PAYLOAD = {
    "articles": [
        {
            "url": "https://www.reuters.com/world/article-1",
            "title": "Trump announces summit",
            "seendate": "20260423T140300Z",
            "domain": "reuters.com",
            "language": "English",
        },
        {
            "url": "https://www.reuters.com/world/article-1",  # duplicate
            "title": "Trump announces summit",
            "seendate": "20260423T140400Z",
            "domain": "reuters.com",
            "language": "English",
        },
        {
            "url": "https://bbc.co.uk/news/article-2",
            "title": "UN responds",
            "seendate": "20260423T145000Z",
            "domain": "bbc.co.uk",
            "language": "English",
        },
    ]
}


@pytest.mark.asyncio
async def test_fetch_recent_parses_and_dedupes():
    client = GdeltClient()
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=SAMPLE_PAYLOAD)
    mock_response.raise_for_status = lambda: None
    with patch.object(client, "_get", new=AsyncMock(return_value=SAMPLE_PAYLOAD)):
        arts = await client.fetch_recent("trump", timespan="15min")
    urls = [a["url"] for a in arts]
    assert len(arts) == 2
    assert "https://www.reuters.com/world/article-1" in urls
    assert "https://bbc.co.uk/news/article-2" in urls


@pytest.mark.asyncio
async def test_fetch_recent_extracts_source_name_from_domain():
    client = GdeltClient()
    with patch.object(client, "_get", new=AsyncMock(return_value=SAMPLE_PAYLOAD)):
        arts = await client.fetch_recent("trump")
    reuters = next(a for a in arts if "reuters" in a["url"])
    assert reuters["source_name"] == "reuters.com"


@pytest.mark.asyncio
async def test_fetch_recent_parses_seendate():
    client = GdeltClient()
    with patch.object(client, "_get", new=AsyncMock(return_value=SAMPLE_PAYLOAD)):
        arts = await client.fetch_recent("trump")
    a0 = arts[0]
    assert a0["publish_date"].isoformat().startswith("2026-04-23T14:03")
