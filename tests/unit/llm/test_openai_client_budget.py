"""Circuit-breaker tests for OpenAIClient — `llm_cost_alert_usd`.

These exercise `_ensure_under_budget` + `_record_call_cost` in isolation,
so they don't need a real OpenAI key or a live database. The DB read is
patched on `_fetch_24h_cost_from_db`; the `chat_completion` integration
test stubs both the cost-fetch and the OpenAI HTTP layer.

Each test resets the module-level cache via `_reset_cost_state_for_tests`
so cache state never leaks between cases.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import app.llm.openai_client as oc_mod
from app.llm.openai_client import (
    LLMBudgetExceeded,
    OpenAIClient,
    _compute_cost_usd,
    _ensure_under_budget,
    _record_call_cost,
    _reset_cost_state_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_breaker_state():
    """Each test starts with a clean cache."""
    _reset_cost_state_for_tests()
    yield
    _reset_cost_state_for_tests()


# ---------------------------------------------------------------------------
# _ensure_under_budget — stale cache forces a DB read, breaker behaviour.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_under_budget_does_not_raise():
    """Sum below threshold → no raise, cache populated."""
    with patch.object(oc_mod, "_fetch_24h_cost_from_db", new=AsyncMock(return_value=5.0)):
        with patch.object(oc_mod.settings, "llm_cost_alert_usd", 30.0):
            await _ensure_under_budget()
    assert oc_mod._COST_STATE["total_usd_24h"] == 5.0


@pytest.mark.asyncio
async def test_over_budget_trips_breaker():
    """Sum >= threshold → LLMBudgetExceeded."""
    with patch.object(oc_mod, "_fetch_24h_cost_from_db", new=AsyncMock(return_value=42.5)):
        with patch.object(oc_mod.settings, "llm_cost_alert_usd", 30.0):
            with pytest.raises(LLMBudgetExceeded) as exc:
                await _ensure_under_budget()
    assert "$42.50" in str(exc.value)
    assert "$30.00" in str(exc.value)


@pytest.mark.asyncio
async def test_breaker_at_exactly_threshold_trips():
    """Threshold-equal is >= and trips — operator sees the alert at the boundary."""
    with patch.object(oc_mod, "_fetch_24h_cost_from_db", new=AsyncMock(return_value=30.0)):
        with patch.object(oc_mod.settings, "llm_cost_alert_usd", 30.0):
            with pytest.raises(LLMBudgetExceeded):
                await _ensure_under_budget()


@pytest.mark.asyncio
async def test_zero_threshold_disables_breaker():
    """Setting <= 0 is the documented escape hatch (e.g. dev seeding)."""
    with patch.object(oc_mod, "_fetch_24h_cost_from_db", new=AsyncMock(return_value=999.0)) as fetch:
        with patch.object(oc_mod.settings, "llm_cost_alert_usd", 0.0):
            await _ensure_under_budget()
    fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_negative_threshold_disables_breaker():
    with patch.object(oc_mod, "_fetch_24h_cost_from_db", new=AsyncMock(return_value=999.0)) as fetch:
        with patch.object(oc_mod.settings, "llm_cost_alert_usd", -1.0):
            await _ensure_under_budget()
    fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_db_failure_falls_back_to_cached_total():
    """A DB error must NOT block every LLM call — fall back to cache."""
    # Seed the cache below threshold so the cached path lets the call through.
    oc_mod._COST_STATE["total_usd_24h"] = 1.0
    oc_mod._COST_STATE["fetched_at_monotonic"] = 0.0  # forces refresh attempt
    with patch.object(
        oc_mod, "_fetch_24h_cost_from_db",
        new=AsyncMock(side_effect=RuntimeError("db down")),
    ):
        with patch.object(oc_mod.settings, "llm_cost_alert_usd", 30.0):
            await _ensure_under_budget()  # must not raise
    # Cache was not corrupted — it kept the 1.0 it already had.
    assert oc_mod._COST_STATE["total_usd_24h"] == 1.0


@pytest.mark.asyncio
async def test_cache_is_reused_within_ttl():
    """Second call within 60 s uses the cached total — no second DB hit."""
    fetch = AsyncMock(return_value=10.0)
    with patch.object(oc_mod, "_fetch_24h_cost_from_db", new=fetch):
        with patch.object(oc_mod.settings, "llm_cost_alert_usd", 30.0):
            await _ensure_under_budget()
            await _ensure_under_budget()
            await _ensure_under_budget()
    fetch.assert_awaited_once()


# ---------------------------------------------------------------------------
# _record_call_cost — increments cached total atomically.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_call_cost_adds_to_running_total():
    oc_mod._COST_STATE["total_usd_24h"] = 4.0
    await _record_call_cost(0.5)
    assert oc_mod._COST_STATE["total_usd_24h"] == 4.5


@pytest.mark.asyncio
async def test_burst_inside_ttl_window_can_trip_via_local_increments():
    """If a burst pushes us over while the TTL is still warm, the next
    `_ensure_under_budget` (no refresh) should still trip on the local
    tally — that's what `_record_call_cost` is for."""
    # Prime: 60 s TTL has not elapsed; cached total is just below threshold.
    with patch.object(oc_mod, "_fetch_24h_cost_from_db", new=AsyncMock(return_value=29.0)):
        with patch.object(oc_mod.settings, "llm_cost_alert_usd", 30.0):
            await _ensure_under_budget()  # caches 29.0, marks fetched_at=now

            # Local burst: 5 calls, $0.50 each, totalling $2.50 → 31.5
            for _ in range(5):
                await _record_call_cost(0.5)

            # No DB hit because the cache is fresh; the in-memory tally
            # alone must trip the breaker.
            with pytest.raises(LLMBudgetExceeded):
                await _ensure_under_budget()


# ---------------------------------------------------------------------------
# _compute_cost_usd — pricing table.
# ---------------------------------------------------------------------------


def test_compute_cost_usd_for_known_model():
    # gpt-4o-mini: $0.15 / 1M input, $0.60 / 1M output
    cost = _compute_cost_usd("gpt-4o-mini", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == pytest.approx(0.75)


def test_compute_cost_usd_unknown_model_falls_back_to_mini():
    cost_known = _compute_cost_usd("gpt-4o-mini", 100_000, 50_000)
    cost_unknown = _compute_cost_usd("some-future-model", 100_000, 50_000)
    assert cost_known == cost_unknown


# ---------------------------------------------------------------------------
# OpenAIClient.chat_completion — breaker prevents the OpenAI HTTP call.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_completion_skips_openai_when_breaker_tripped():
    """When budget is blown, `chat_completion` raises before any HTTP call."""
    client = OpenAIClient(api_key="sk-test")
    fake_create = AsyncMock(return_value=None)
    client._client.chat.completions.create = fake_create  # type: ignore[assignment]

    with patch.object(oc_mod, "_fetch_24h_cost_from_db", new=AsyncMock(return_value=999.0)):
        with patch.object(oc_mod.settings, "llm_cost_alert_usd", 30.0):
            with pytest.raises(LLMBudgetExceeded):
                await client.chat_completion(
                    messages=[{"role": "user", "content": "hi"}],
                    call_type="test",
                )

    fake_create.assert_not_awaited()
