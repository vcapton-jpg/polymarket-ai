"""fetch_gdelt task — resolve/auto-create source, insert news with source_id."""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, text

from app.db.database import get_session_factory
from app.db.models import News, SourceRegistry
from app.workers.tasks_ingestion import _fetch_gdelt_async


CANNED = [
    {
        "url": "https://newdomain.example.com/a",
        "title": "Breaking news",
        "text": "",
        "source_name": "newdomain.example.com",
        "publish_date": None,
        "language": "english",
    }
]


@pytest.mark.asyncio
async def test_fetch_gdelt_autocreates_source_and_inserts_news():
    session_factory = get_session_factory()
    async with session_factory() as s:
        await s.execute(text(
            "DELETE FROM news WHERE source_name='newdomain.example.com'"
        ))
        await s.execute(text(
            "DELETE FROM sources_registry WHERE source_name='newdomain.example.com'"
        ))
        await s.commit()

    with patch(
        "app.workers.tasks_ingestion.GdeltClient.fetch_recent",
        new=AsyncMock(return_value=CANNED),
    ):
        inserted = await _fetch_gdelt_async(queries=["trump"])

    assert inserted >= 1
    async with session_factory() as s:
        src = (await s.execute(
            select(SourceRegistry).where(SourceRegistry.source_name == "newdomain.example.com")
        )).scalar_one()
        assert src.tier == 3
        assert abs((src.weight or 0) - 0.4) < 1e-6
        assert src.source_type == "gdelt_auto"

        n = (await s.execute(
            select(News).where(News.source_name == "newdomain.example.com")
        )).scalar_one()
        assert n.source_id == src.id
