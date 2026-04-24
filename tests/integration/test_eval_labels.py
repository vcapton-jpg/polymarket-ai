"""Integration tests for app.eval.labels — DB heuristic loaders only (task 4)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models import (
    Event,
    EventMarketAnalysis,
    EventMarketCandidate,
    EventNewsLink,
    Market,
    News,
    NewsClean,
    Signal,
    SignalArticle,
)
from app.eval.labels import EvalPair, load_pairs  # noqa: F401 (EvalPair re-export smoke-check)


NOW = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
async def labels_corpus(async_db_factory):
    """Seeds a tiny corpus exercising all three DB-heuristic surfaces."""
    async with async_db_factory() as s:
        # 2 events, 3 markets, 4 news, 1 signal with articles.
        ev1 = Event(id=9001, event_title="Ev1", first_seen=NOW, last_seen=NOW, bucket="politics")
        ev2 = Event(id=9002, event_title="Ev2", first_seen=NOW, last_seen=NOW, bucket="politics")
        m1 = Market(market_id="m1", question="q1", active=True, closed=False, accepting_orders=True)
        m2 = Market(market_id="m2", question="q2", active=True, closed=False, accepting_orders=True)
        m3 = Market(market_id="m3", question="q3", active=True, closed=False, accepting_orders=True)
        n1 = News(id=7001, source_name="src", source_tier=1, title="t1", url="http://x/1",
                  ingestion_date=NOW, publish_date=NOW)
        n2 = News(id=7002, source_name="src", source_tier=1, title="t2", url="http://x/2",
                  ingestion_date=NOW, publish_date=NOW)
        nc1 = NewsClean(id=7101, news_id=7001, clean_text="c1")
        nc2 = NewsClean(id=7102, news_id=7002, clean_text="c2")
        s.add_all([ev1, ev2, m1, m2, m3, n1, n2, nc1, nc2])
        await s.flush()

        # event_to_market: 2 positives for ev1 (m1 rank=1, m2 rank=2), 1 outside (m3 rank=5)
        s.add_all([
            EventMarketCandidate(event_id=9001, market_id="m1", rank=1, cosine_score=0.9, rrf_score=0.9),
            EventMarketCandidate(event_id=9001, market_id="m2", rank=2, cosine_score=0.8, rrf_score=0.8),
            EventMarketCandidate(event_id=9001, market_id="m3", rank=5, cosine_score=0.3, rrf_score=0.3),
            EventMarketAnalysis(event_id=9001, market_id="m1", impact_strength=0.8),
            EventMarketAnalysis(event_id=9001, market_id="m2", impact_strength=0.5),
            # No analysis row for m3 → excluded from positives.
        ])

        # article_to_event: ev1 ← {nc1 primary}, ev2 ← {nc2 primary}
        s.add_all([
            EventNewsLink(event_id=9001, clean_id=7101, role="primary"),
            EventNewsLink(event_id=9001, clean_id=7102, role="supporting"),  # NOT primary
            EventNewsLink(event_id=9002, clean_id=7102, role="primary"),
        ])

        # market_to_article: signal 6001 (on m1) picked 2 articles via variant "signal"
        sig = Signal(
            id=6001,
            market_id="m1",
            event_id=9001,
            created_at=NOW,
            signal_score=80.0,
            direction="BUY_YES",
            market_price_at_signal=0.5,
        )
        s.add(sig)
        await s.flush()
        s.add_all([
            SignalArticle(signal_id=6001, variant="signal", news_clean_id=7101,
                          rank=1, score=0.9, cosine_score=0.9, recency_weight=1.0),
            SignalArticle(signal_id=6001, variant="signal", news_clean_id=7102,
                          rank=2, score=0.8, cosine_score=0.8, recency_weight=0.95),
        ])
        await s.commit()

    yield

    # Teardown — explicit, FK-ordered, so the next test starts clean.
    async with async_db_factory() as s:
        await s.execute(delete(SignalArticle).where(SignalArticle.signal_id == 6001))
        await s.execute(delete(Signal).where(Signal.id == 6001))
        await s.execute(
            delete(EventNewsLink).where(EventNewsLink.event_id.in_([9001, 9002]))
        )
        await s.execute(
            delete(EventMarketAnalysis).where(EventMarketAnalysis.event_id == 9001)
        )
        await s.execute(
            delete(EventMarketCandidate).where(EventMarketCandidate.event_id == 9001)
        )
        await s.execute(delete(NewsClean).where(NewsClean.id.in_([7101, 7102])))
        await s.execute(delete(News).where(News.id.in_([7001, 7002])))
        await s.execute(delete(Market).where(Market.market_id.in_(["m1", "m2", "m3"])))
        await s.execute(delete(Event).where(Event.id.in_([9001, 9002])))
        await s.commit()


async def test_load_pairs_event_to_market_uses_rank_le_3_and_analysis_present(
    labels_corpus, async_db_factory
):
    async with async_db_factory() as s:
        pairs = await load_pairs(s, surface="event_to_market", limit=500)
    ev1_pairs = [p for p in pairs if p.query_id == 9001]
    assert len(ev1_pairs) == 1
    assert ev1_pairs[0].relevant_ids == {"m1", "m2"}
    assert ev1_pairs[0].source == "db_heuristic"


async def test_load_pairs_article_to_event_uses_primary_role(
    labels_corpus, async_db_factory
):
    async with async_db_factory() as s:
        pairs = await load_pairs(s, surface="article_to_event", limit=500)
    # nc1 → ev1 (primary), nc2 → ev2 (primary). nc2→ev1 is supporting, excluded.
    by_q = {p.query_id: p.relevant_ids for p in pairs}
    assert 7101 in by_q and by_q[7101] == {9001}
    assert 7102 in by_q and by_q[7102] == {9002}


async def test_load_pairs_market_to_article_uses_signal_articles_variant_signal(
    labels_corpus, async_db_factory
):
    async with async_db_factory() as s:
        pairs = await load_pairs(s, surface="market_to_article", limit=500)
    m1_pairs = [p for p in pairs if p.query_id == "m1"]
    assert len(m1_pairs) == 1
    assert m1_pairs[0].relevant_ids == {7101, 7102}


async def test_load_pairs_invalid_surface_raises(async_db_factory):
    async with async_db_factory() as s:
        with pytest.raises(ValueError, match="surface"):
            await load_pairs(s, surface="not_a_real_surface")
