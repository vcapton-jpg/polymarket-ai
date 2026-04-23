"""rss_scraper.fetch_sources propagates source_id from the registry entry."""
from unittest.mock import AsyncMock, patch

import pytest

from app.ingestion.rss_scraper import fetch_sources


@pytest.mark.asyncio
async def test_fetch_sources_propagates_source_id():
    src = {
        "id": 42,
        "source_name": "test-src",
        "source_type": "rss",
        "url": "https://example.com/feed.xml",
        "tier": 1,
        "weight": 0.9,
    }
    canned_feed = [
        {
            "url": "https://example.com/a",
            "title": "Hello",
            "text": "body",
            "publish_date": None,
        }
    ]
    with patch(
        "app.ingestion.rss_scraper.fetch_feed",
        new=AsyncMock(return_value=canned_feed),
    ):
        arts = await fetch_sources([src])

    assert len(arts) == 1
    assert arts[0]["source_id"] == 42
    assert arts[0]["source_name"] == "test-src"
    assert arts[0]["source_tier"] == 1


@pytest.mark.asyncio
async def test_fetch_sources_source_id_is_none_when_missing():
    src = {
        "source_name": "legacy",
        "source_type": "rss",
        "url": "https://example.com/feed.xml",
        "tier": 2,
        "weight": 0.5,
    }
    canned_feed = [
        {
            "url": "https://example.com/b",
            "title": "Legacy",
            "text": "body",
            "publish_date": None,
        }
    ]
    with patch(
        "app.ingestion.rss_scraper.fetch_feed",
        new=AsyncMock(return_value=canned_feed),
    ):
        arts = await fetch_sources([src])

    assert arts[0]["source_id"] is None
