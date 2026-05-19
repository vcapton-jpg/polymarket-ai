"""Pin the Polymarket deep-link fix (2026-05-19).

Every "Voir sur Polymarket" link was broken: the API emitted
`https://polymarket.com/market/<conditionId>`, which 307-redirects to
`/404` (verified live). Polymarket web only resolves
`https://polymarket.com/event/<slug>`. This locks the corrected
builder so the broken form can never come back.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.api.signal_mapper import polymarket_url


def test_uses_event_slug_when_present():
    m = SimpleNamespace(slug="microstrategy-sell-any-bitcoin-in-2025")
    assert (
        polymarket_url(m)
        == "https://polymarket.com/event/microstrategy-sell-any-bitcoin-in-2025"
    )


def test_never_emits_broken_market_path():
    # The old form `/market/<conditionId>` 307s → /404. Guard it.
    m = SimpleNamespace(slug="some-event-slug")
    url = polymarket_url(m)
    assert "/market/" not in url
    assert url.startswith("https://polymarket.com/event/")


def test_safe_fallback_when_slug_missing():
    # Slug not yet ingested → Polymarket home (HTTP 200), never a dead
    # deep link. Backfills within one ingest cycle.
    assert polymarket_url(SimpleNamespace(slug=None)) == "https://polymarket.com"


def test_safe_fallback_when_market_none():
    assert polymarket_url(None) == "https://polymarket.com"


def test_no_conditionid_leaks_into_url():
    # Even if a caller passes an object that only has a market_id, we
    # must NOT fall back to the broken /market/<id> form.
    m = SimpleNamespace(market_id="0xdeadbeef", slug=None)
    assert polymarket_url(m) == "https://polymarket.com"
