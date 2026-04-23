"""On 429, the signal is pushed to signals_pending_reasoning instead of persisted."""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.db.database import get_session_factory
from app.db.models import Signal, SignalPendingReasoning
from app.workers.tasks_scoring import _score_event_market_async


@pytest.mark.asyncio
async def test_quota_exceeded_writes_pending_row():
    class Quota429(Exception):
        pass

    analyzer = AsyncMock()
    analyzer.model_version = "gpt-4o-mini-2024-07-18"
    analyzer.analyze = AsyncMock(side_effect=Quota429("insufficient_quota"))

    event = {"id": 1, "title": "t", "summary": "s"}
    market = {"id": "m-quota-test", "question": "q?", "price": 0.5}
    articles = [{
        "news_clean_id": 1, "title": "x", "source_name": "Reuters Top News",
        "source_tier": 1, "clean_text": "body", "publish_date": None,
    }]

    with patch("app.workers.tasks_scoring._is_quota_error", return_value=True):
        out = await _score_event_market_async(event, market, articles, analyzer=analyzer)
    assert out is None

    session_factory = get_session_factory()
    async with session_factory() as s:
        row = (await s.execute(
            select(SignalPendingReasoning).where(SignalPendingReasoning.market_id == "m-quota-test")
        )).scalar_one_or_none()
        assert row is not None
        assert row.event_id == 1
        no_sig = (await s.execute(
            select(Signal).where(Signal.market_id == "m-quota-test")
        )).scalar_one_or_none()
        assert no_sig is None
        await s.delete(row)
        await s.commit()
