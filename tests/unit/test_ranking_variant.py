"""Tests for the ranking-variant dispatcher."""
from __future__ import annotations

import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_active_ranking_variant_defaults_to_v1():
    from app.retrieval.ranking_variant import active_ranking_variant
    assert active_ranking_variant() == "v1"


def test_active_ranking_variant_returns_v2(monkeypatch):
    monkeypatch.setenv("RANKING_VARIANT_EVENT_TO_MARKET", "v2")
    get_settings.cache_clear()
    from app.retrieval.ranking_variant import active_ranking_variant
    assert active_ranking_variant() == "v2"


def test_active_ranking_variant_falls_back_on_garbage(monkeypatch):
    monkeypatch.setenv("RANKING_VARIANT_EVENT_TO_MARKET", "v99")
    get_settings.cache_clear()
    from app.retrieval.ranking_variant import active_ranking_variant
    assert active_ranking_variant() == "v1"


@pytest.mark.asyncio
async def test_dispatcher_routes_to_v1(monkeypatch):
    """Dispatcher with variant=v1 delegates to hybrid_search.hybrid_search_markets."""
    captured: dict = {}

    async def fake_v1(session, emb, text, **kwargs):
        captured["variant"] = "v1"
        return [{"market_id": "m1", "rrf_score": 0.1, "rank": 1}]

    monkeypatch.setattr(
        "app.retrieval.hybrid_search.hybrid_search_markets", fake_v1
    )

    from app.retrieval.ranking_variant import hybrid_search_markets_dispatch
    out = await hybrid_search_markets_dispatch(None, [0.0] * 1536, "hello")
    assert captured["variant"] == "v1"
    assert out and out[0]["market_id"] == "m1"


@pytest.mark.asyncio
async def test_dispatcher_routes_to_v2_when_flag_set(monkeypatch):
    monkeypatch.setenv("RANKING_VARIANT_EVENT_TO_MARKET", "v2")
    get_settings.cache_clear()

    captured: dict = {}

    async def fake_v2(session, emb, text, **kwargs):
        captured["variant"] = "v2"
        return [{"market_id": "m2", "rrf_score": 0.2, "rank": 1}]

    # The v2 module will be imported lazily inside the dispatcher; monkeypatch
    # it *after* importing so the symbol exists.
    import app.retrieval.hybrid_search_v2  # noqa: F401
    monkeypatch.setattr(
        "app.retrieval.hybrid_search_v2.hybrid_search_markets_v2", fake_v2
    )

    from app.retrieval.ranking_variant import hybrid_search_markets_dispatch
    out = await hybrid_search_markets_dispatch(None, [0.0] * 1536, "hello")
    assert captured["variant"] == "v2"
    assert out[0]["market_id"] == "m2"
