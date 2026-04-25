"""Activation tests for the news_sentiment + momentum_24h baselines.

Background (audit 2026-04-25, items I + II):

    Up to commit 1ef4383 the prod scoring path called
    `record_baselines_for_signal(session, signal=best_signal, articles=[])`
    with an empty article list and no `market_price_24h_ago`. The result:

      • baseline_news_sentiment → returns None (no articles) → no row written
      • baseline_momentum       → returns None (no 24h price) → no row written

    Two of the four chantier-#1 baselines were dormant in prod, defeating the
    point of the harness.

This module pins the wiring fix in three layers:

  1. `_fetch_baseline_articles` recovers per-article `source_weight` from the
     News table via the EventNewsLink → NewsClean → News join.
  2. `_fetch_market_price_24h_ago` resolves the YES token id from
     `Market.clob_token_ids` and asks ClobClient for the 24h-old price,
     swallowing all network failures (returns None).
  3. End-to-end: `_run_full_scoring_pipeline`'s exact wiring block (articles
     list + 24h price flowing into `record_baselines_for_signal`) writes
     non-null `predicted_probability` rows for both baselines.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.db.models import (
    Event,
    EventNewsLink,
    Market,
    News,
    NewsClean,
    Signal,
    SignalPrediction,
)
from app.workers import tasks_scoring as ts


# ── _fetch_baseline_articles ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_baseline_articles_returns_source_weights(async_db_factory):
    """Two linked articles → two rows with the correct source_weight values.

    Ordering: EventNewsLink.relevance_score DESC NULLS LAST. We seed two links
    with different relevance scores so the order is deterministic.
    """
    EVENT_ID = 992100
    URLS = [
        "https://example.com/baseline-articles-1",
        "https://example.com/baseline-articles-2",
    ]

    async with async_db_factory() as s:
        s.add(Event(id=EVENT_ID, event_title="e"))
        n1 = News(
            url=URLS[0], title="t1", source_name="reuters",
            source_tier=1, source_weight=0.95,
        )
        n2 = News(
            url=URLS[1], title="t2", source_name="randomblog",
            source_tier=3, source_weight=0.30,
        )
        s.add_all([n1, n2])
        await s.flush()
        c1 = NewsClean(news_id=n1.id, clean_text="t1 body")
        c2 = NewsClean(news_id=n2.id, clean_text="t2 body")
        s.add_all([c1, c2])
        await s.flush()
        s.add(EventNewsLink(event_id=EVENT_ID, clean_id=c1.id, relevance_score=0.9))
        s.add(EventNewsLink(event_id=EVENT_ID, clean_id=c2.id, relevance_score=0.4))
        await s.commit()

    try:
        async with async_db_factory() as s:
            arts = await ts._fetch_baseline_articles(s, event_id=EVENT_ID)
            assert len(arts) == 2
            # ordered by relevance DESC: 0.95 first, 0.30 second
            assert arts[0]["source_weight"] == pytest.approx(0.95)
            assert arts[1]["source_weight"] == pytest.approx(0.30)
            # Critically: NO `direction` key — defaults to NEUTRAL in the
            # ScoringContext builder. Future chantiers can add per-article
            # direction without touching this fetch helper.
            assert "direction" not in arts[0]
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(EventNewsLink).where(EventNewsLink.event_id == EVENT_ID))
            await s.execute(delete(NewsClean).where(NewsClean.news.has(News.url.in_(URLS))))
            await s.execute(delete(News).where(News.url.in_(URLS)))
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.commit()


@pytest.mark.asyncio
async def test_fetch_baseline_articles_empty_when_no_links(async_db_factory):
    """Event with no linked articles → empty list (baseline returns None,
    no row written for news_sentiment — that's the desired behaviour)."""
    EVENT_ID = 992101

    async with async_db_factory() as s:
        s.add(Event(id=EVENT_ID, event_title="e-empty"))
        await s.commit()

    try:
        async with async_db_factory() as s:
            arts = await ts._fetch_baseline_articles(s, event_id=EVENT_ID)
            assert arts == []
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.commit()


@pytest.mark.asyncio
async def test_fetch_baseline_articles_swallows_db_failure(monkeypatch):
    """A broken session must not propagate — measurement is non-fatal."""

    class _BoomSession:
        async def execute(self, *_a, **_kw):
            raise RuntimeError("simulated DB failure")

    arts = await ts._fetch_baseline_articles(_BoomSession(), event_id=1)
    assert arts == []


# ── _fetch_market_price_24h_ago ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_24h_price_returns_none_when_market_missing():
    assert await ts._fetch_market_price_24h_ago(None) is None


@pytest.mark.asyncio
async def test_fetch_24h_price_returns_none_when_no_clob_tokens():
    """Markets ingested before clob_token_ids was added don't have YES/NO ids."""

    class _M:
        clob_token_ids = None

    assert await ts._fetch_market_price_24h_ago(_M()) is None

    class _M2:
        clob_token_ids = {"no": "n1"}  # missing the "yes" key

    assert await ts._fetch_market_price_24h_ago(_M2()) is None


@pytest.mark.asyncio
async def test_fetch_24h_price_calls_clob_client(monkeypatch):
    """Happy path: token id present → ClobClient.get_price_24h_ago invoked
    and its return value bubbles up. Also asserts the client is closed
    (no leaked httpx connection)."""

    calls: dict[str, object] = {}

    class _FakeClient:
        def __init__(self):
            calls["init"] = True

        async def get_price_24h_ago(self, token_id):
            calls["token_id"] = token_id
            return 0.42

        async def close(self):
            calls["closed"] = True

    monkeypatch.setattr(ts, "_fetch_market_price_24h_ago", ts._fetch_market_price_24h_ago)
    # Patch the ClobClient symbol where the helper imports it from.
    from app.polymarket import clob_client as cc_mod
    monkeypatch.setattr(cc_mod, "ClobClient", _FakeClient)

    class _Market:
        clob_token_ids = {"yes": "yes-token-xyz", "no": "no-token-xyz"}

    price = await ts._fetch_market_price_24h_ago(_Market())
    assert price == 0.42
    assert calls["token_id"] == "yes-token-xyz"
    assert calls["closed"] is True


@pytest.mark.asyncio
async def test_fetch_24h_price_swallows_clob_error(monkeypatch):
    """Polymarket outages must not abort the signal commit."""

    class _BoomClient:
        async def get_price_24h_ago(self, _token_id):
            raise RuntimeError("simulated CLOB outage")

        async def close(self):
            pass

    from app.polymarket import clob_client as cc_mod
    monkeypatch.setattr(cc_mod, "ClobClient", _BoomClient)

    class _Market:
        clob_token_ids = {"yes": "tok"}

    assert await ts._fetch_market_price_24h_ago(_Market()) is None


# ── End-to-end: prod wiring activates both baselines ──────────────────────


@pytest.mark.asyncio
async def test_prod_wiring_activates_news_sentiment_and_momentum(async_db_factory):
    """Mirror the exact code block in `_run_full_scoring_pipeline` after the
    `await session.flush()` — fetch articles, fetch 24h price (mocked),
    call `record_baselines_for_signal`. Assert both baselines now produce
    non-null predicted_probability.

    This is the regression net for items (I) and (II) of the 2026-04-25
    audit: if a future change drops articles or the 24h-price plumbing,
    these baselines silently revert to None and this test fails.
    """
    import app.measurement  # noqa: F401  (registers baselines)
    from app.measurement.pipeline import record_baselines_for_signal

    EVENT_ID = 992200
    MARKET_ID = "0xprod-wire-data-1"
    URL = "https://example.com/prod-wire-data-1"

    async with async_db_factory() as s:
        s.add(Market(
            market_id=MARKET_ID, question="q", active=True,
            clob_token_ids={"yes": "yes-tok", "no": "no-tok"},
        ))
        s.add(Event(id=EVENT_ID, event_title="e"))
        n = News(
            url=URL, title="t", source_name="reuters",
            source_tier=1, source_weight=0.9,
        )
        s.add(n)
        await s.flush()
        c = NewsClean(news_id=n.id, clean_text="body")
        s.add(c)
        await s.flush()
        s.add(EventNewsLink(event_id=EVENT_ID, clean_id=c.id, relevance_score=0.9))
        await s.commit()

    try:
        # Force `_fetch_market_price_24h_ago` to return a known, distinct
        # value so we can verify the momentum baseline picked it up.
        async def _stub_24h(market):
            return 0.45  # current price will be 0.55, momentum ⇒ BUY_YES

        # Patch via module attribute (helpers are module-level, so this works).
        original = ts._fetch_market_price_24h_ago
        ts._fetch_market_price_24h_ago = _stub_24h  # type: ignore[assignment]

        try:
            async with async_db_factory() as s:
                # Re-fetch the market (analogous to the loop's `market` var).
                market = (
                    await s.execute(
                        select(Market).where(Market.market_id == MARKET_ID)
                    )
                ).scalar_one()

                sig = Signal(
                    event_id=EVENT_ID,
                    market_id=MARKET_ID,
                    signal_score=72.0,
                    signal_strength=72,
                    trade_quality=60,
                    direction="YES",
                    market_price_at_signal=0.55,
                )
                s.add(sig)
                await s.flush()

                articles = await ts._fetch_baseline_articles(s, event_id=EVENT_ID)
                price_24h = await ts._fetch_market_price_24h_ago(market)
                assert articles, "fetch returned no articles — wiring broken upstream"
                assert price_24h == 0.45

                await record_baselines_for_signal(
                    s,
                    signal=sig,
                    articles=articles,
                    market_price_24h_ago=price_24h,
                )
                await s.commit()

                rows = (
                    await s.execute(
                        select(SignalPrediction).where(
                            SignalPrediction.signal_id == sig.id
                        )
                    )
                ).scalars().all()
                by_variant = {r.variant: r for r in rows}

                # The whole point: both baselines must now have non-null
                # predicted_probability (previously: silently None).
                mom = by_variant["baseline_momentum"]
                assert mom.predicted_probability is not None, (
                    "baseline_momentum still None — market_price_24h_ago "
                    "did not reach the baseline"
                )
                assert mom.predicted_direction == "BUY_YES"  # 0.55 > 0.45

                ns = by_variant["baseline_news_sentiment"]
                assert ns.predicted_probability is not None, (
                    "baseline_news_sentiment still None — articles did "
                    "not reach the baseline"
                )
        finally:
            ts._fetch_market_price_24h_ago = original  # type: ignore[assignment]
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(Signal).where(Signal.market_id == MARKET_ID))
            await s.execute(delete(EventNewsLink).where(EventNewsLink.event_id == EVENT_ID))
            await s.execute(delete(NewsClean).where(NewsClean.news.has(News.url == URL)))
            await s.execute(delete(News).where(News.url == URL))
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.execute(delete(Market).where(Market.market_id == MARKET_ID))
            await s.commit()
