"""P0-1 (audit 2026-04-25): the async `_persist_signal` MUST populate
`signal_strength` and `trade_quality`, not just `signal_score`.

Background: as of the audit, 118 / 311 (37.9%) of prod Signal rows had
NULL `signal_strength`. Cause: the async path through
`app.signal.signal_builder.build_signal -> _persist_signal` constructs a
Signal with only `signal_score` set; the two derived columns the
measurement / ranking layers consume are left NULL.

This test pins the post-fix behaviour: when the async path commits a
signal, the row must have non-NULL `signal_strength` and `trade_quality`.
A regression that removes those assignments will break this test.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, select


@pytest.mark.asyncio
async def test_async_persist_writes_strength_and_trade_quality(async_db_factory):
    from app.db.models import Event, EventNewsLink, Market, News, NewsClean, Signal
    from app.signal.signal_builder import build_signal

    EVENT_ID = 992100
    MARKET_ID = "0xpersist-strength-1"
    NEWS_URL = "https://example.com/persist-strength-1"

    # Seed event/market/news/clean/link so the persist path can attach
    # the excerpt update without warnings.
    async with async_db_factory() as s:
        s.add(Market(market_id=MARKET_ID, question="q", active=True))
        s.add(Event(id=EVENT_ID, event_title="e"))
        n = News(
            url=NEWS_URL, title="t", source_name="reuters",
            source_tier=1, source_weight=0.95,
        )
        s.add(n)
        await s.flush()
        nc = NewsClean(news_id=n.id, clean_text="body text", simhash=0)
        s.add(nc)
        await s.flush()
        s.add(EventNewsLink(event_id=EVENT_ID, clean_id=nc.id))
        await s.commit()
        clean_id = nc.id

    analyzer = AsyncMock()
    analyzer.model_version = "gpt-4o-mini-2024-07-18"
    analyzer.analyze = AsyncMock(return_value={
        "impact_score": 0.8,
        "confidence": 0.9,
        "catalyst": "Test catalyst",
        "reasoning": (
            "Reuters confirms the development, directly addressing the "
            "market resolution criteria. Conviction is high. Direction is YES."
        ),
        "direction_recommendation": "YES",
        "article_excerpts": [
            {"news_clean_id": clean_id, "excerpt": "body text", "relevance": 0.9}
        ],
        "source_tier_mix": {"tier_1": 1},
    })

    try:
        result = await build_signal(
            event={"id": EVENT_ID, "title": "t", "summary": "s"},
            market={"id": MARKET_ID, "question": "q?", "price": 0.55},
            articles=[{
                "news_clean_id": clean_id, "title": "t",
                "source_name": "reuters", "source_tier": 1,
                "clean_text": "body text", "publish_date": None,
            }],
            analyzer=analyzer,
            persist=True,
        )
        assert result is not None

        async with async_db_factory() as s:
            row = (await s.execute(
                select(Signal).where(Signal.market_id == MARKET_ID)
            )).scalar_one()

            # Pin: signal_score must be set (already worked pre-fix).
            assert row.signal_score is not None, "signal_score must be persisted"
            assert float(row.signal_score) > 0

            # PIN (P0-1): the two columns the audit found NULL must now be
            # populated. NULL here = regression to the bug that left 37.9%
            # of prod signals partially scored.
            assert row.signal_strength is not None, (
                "signal_strength is NULL — async _persist_signal regressed "
                "to pre-fix behaviour (audit 2026-04-25 P0-1)."
            )
            assert row.trade_quality is not None, (
                "trade_quality is NULL — async _persist_signal regressed "
                "to pre-fix behaviour (audit 2026-04-25 P0-1)."
            )
            # Sanity: values must be in the documented [0, 100] range.
            assert 0 <= float(row.signal_strength) <= 100
            assert 0 <= float(row.trade_quality) <= 100
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(Signal).where(Signal.market_id == MARKET_ID))
            await s.execute(delete(EventNewsLink).where(EventNewsLink.event_id == EVENT_ID))
            await s.execute(delete(NewsClean).where(NewsClean.news.has(News.url == NEWS_URL)))
            await s.execute(delete(News).where(News.url == NEWS_URL))
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.execute(delete(Market).where(Market.market_id == MARKET_ID))
            await s.commit()
