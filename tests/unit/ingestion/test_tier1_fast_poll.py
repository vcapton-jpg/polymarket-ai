"""Tier-1 fast poll: tier filtering and beat-schedule wiring.

Latency audit 2026-04-27 found tier-1 wire sources (Reuters, FirstSquawk,
@business, AP) had p50 publish→ingestion lag of 4-24 min, mostly due to
the unified 90 s poll interval. Splitting the schedule into a fast
tier-1 path (15 s) and a slow tier-2/3 path (90 s) brings the wire-grade
lag closer to the RSSHub cache TTL floor (~60-75 s).

This test guards the contract:
  • `get_sources_by_tier_and_type` filters correctly
  • Beat schedule has both `fetch-rss-tier1-fast` and `fetch-rss-tier-low`
  • Their schedules are wired to the right config knobs
  • The two cadences cannot collapse to the same value silently
"""
from __future__ import annotations

from app.core.config import Settings
from app.workers.celery_app import _beat_schedule

# ── Config defaults ───────────────────────────────────────────────────────


def test_tier1_poll_default_is_under_30s() -> None:
    """Tier-1 cadence must be aggressive — anything ≥ 30 s is wasted
    given the RSSHub 60 s cache TTL. The latency-critical accounts
    deserve a poll inside the cache window.
    """
    field = Settings.model_fields["tier1_rss_poll_interval_seconds"]
    assert field.default <= 30, (
        f"tier1_rss_poll_interval_seconds={field.default}s — "
        "should be ≤ 30 s to stay aligned with RSSHub's 60 s cache. "
        "Loosening requires a fresh latency audit."
    )


def test_tier1_poll_is_faster_than_tier_low() -> None:
    """The two cadences must NOT collapse to the same value silently.
    A future tweak that sets them equal makes the split pointless.
    """
    fast = Settings.model_fields["tier1_rss_poll_interval_seconds"].default
    slow = Settings.model_fields["rss_poll_interval_seconds"].default
    assert fast < slow, (
        f"tier1_rss_poll_interval_seconds ({fast}s) must be strictly "
        f"smaller than rss_poll_interval_seconds ({slow}s) — "
        "otherwise the split-cadence design is moot."
    )


# ── Beat schedule wiring ─────────────────────────────────────────────────


def test_beat_has_separate_tier1_and_tier_low_entries() -> None:
    """Both tasks must exist as distinct entries. A common bug after
    refactor would be to keep only one and wonder why the other tier
    isn't polled at all.
    """
    assert "fetch-rss-tier1-fast" in _beat_schedule, (
        "fetch-rss-tier1-fast missing from beat schedule"
    )
    assert "fetch-rss-tier-low" in _beat_schedule, (
        "fetch-rss-tier-low missing from beat schedule"
    )


def test_beat_tier1_uses_dedicated_task_not_legacy_alias() -> None:
    """The fast entry must point at `fetch_rss_tier1`, NOT at the
    legacy `fetch_rss_feeds`. If pointed at the legacy task, every
    fast tick would re-poll all tiers — defeating the rate-limit
    rationale on the upstream feeds.
    """
    fast = _beat_schedule["fetch-rss-tier1-fast"]
    assert fast["task"] == "app.workers.tasks_ingestion.fetch_rss_tier1", (
        f"fetch-rss-tier1-fast points at {fast['task']!r} — "
        "expected app.workers.tasks_ingestion.fetch_rss_tier1"
    )

    slow = _beat_schedule["fetch-rss-tier-low"]
    assert slow["task"] == "app.workers.tasks_ingestion.fetch_rss_feeds"


def test_beat_tier1_schedule_uses_tier1_config_knob() -> None:
    """The fast entry's schedule must equal `tier1_rss_poll_interval_seconds`
    — not a hardcoded number, not `rss_poll_interval_seconds`.
    """
    fast = _beat_schedule["fetch-rss-tier1-fast"]
    expected = Settings.model_fields["tier1_rss_poll_interval_seconds"].default
    assert fast["schedule"] == expected, (
        f"fetch-rss-tier1-fast schedule={fast['schedule']} != "
        f"tier1_rss_poll_interval_seconds={expected}. "
        "Hardcoding the value here means future config tweaks won't take effect."
    )


# ── Tier filter helper ────────────────────────────────────────────────────


def test_get_sources_by_tier_and_type_filters_correctly() -> None:
    """Pure unit test on the cache filter — no DB needed."""
    from app.ingestion import sources_registry as sr

    # Seed cache with known fixture
    sr._sources_cache.clear()
    sr._sources_cache.update({
        "X: @Reuters":      {"id": 1, "source_name": "X: @Reuters",     "source_type": "x_rss", "tier": 1, "weight": 1.0, "url": "http://x"},
        "X: @business":     {"id": 2, "source_name": "X: @business",    "source_type": "x_rss", "tier": 1, "weight": 0.85, "url": "http://x"},
        "Reuters Top News": {"id": 3, "source_name": "Reuters Top News","source_type": "rss",   "tier": 1, "weight": 1.0, "url": "http://r"},
        "World News API":   {"id": 4, "source_name": "World News API",  "source_type": "api",   "tier": 2, "weight": 0.7, "url": "http://w"},
        "Metaculus RSS":    {"id": 5, "source_name": "Metaculus RSS",   "source_type": "rss",   "tier": 3, "weight": 0.35, "url": "http://m"},
    })

    import asyncio

    async def _run():
        tier1_rss = await sr.get_sources_by_tier_and_type(
            (1,), ("rss", "x_rss"),
        )
        return [s["source_name"] for s in tier1_rss]

    names = asyncio.run(_run())
    assert "X: @Reuters" in names
    assert "X: @business" in names
    assert "Reuters Top News" in names
    assert "World News API" not in names    # api type excluded
    assert "Metaculus RSS" not in names      # tier 3 excluded


def test_get_sources_by_tier_and_type_excludes_other_types() -> None:
    """A tier-1 source with type 'api' must NOT show up in the
    rss/x_rss filter — otherwise we'd poll it via the wrong path."""
    from app.ingestion import sources_registry as sr

    sr._sources_cache.clear()
    sr._sources_cache.update({
        "Wire API": {"id": 1, "source_name": "Wire API", "source_type": "api", "tier": 1, "weight": 1.0, "url": "http://"},
    })

    import asyncio

    async def _run():
        return await sr.get_sources_by_tier_and_type((1,), ("rss", "x_rss"))

    assert asyncio.run(_run()) == []
