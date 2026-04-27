"""compute_event_seen_window: derive (first_seen, last_seen) from article timestamps.

The fast-path at `tasks_pipeline._try_instant_event_async` was creating
events with `last_seen` = NOW (DB server_default kicked in because the
constructor didn't set the field). That made stale-news clusters look
freshly-arrived and slipped past `signal_event_max_age_hours = 6h`,
emitting signals on tweets >6h old.

This helper is the single source of truth for "what timestamps does
the cluster anchor on?", so both `event_builder.py` (batch path) and
`tasks_pipeline.py` (fast path) compute identical values.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.processing.freshness import compute_event_seen_window


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 4, 27, 7, 0, 0, tzinfo=timezone.utc)


def test_returns_now_for_empty_cluster(now: datetime) -> None:
    """Defensive: empty cluster returns (now, now). Should never happen
    in practice (fast path requires ≥ min_articles) but the helper
    must not crash."""
    first, last = compute_event_seen_window([], at=now)
    assert first == now
    assert last == now


def test_uses_publish_date_when_both_available(now: datetime) -> None:
    """publish_date is the authoritative timestamp. ingestion_date is
    later (network/scrape lag). Conservative reference is the OLDER of
    the two — in this case publish_date."""
    publish = now - timedelta(hours=17)
    ingest = now - timedelta(hours=15)
    first, last = compute_event_seen_window([(publish, ingest)], at=now)
    assert first == publish
    assert last == publish


def test_falls_back_to_ingestion_when_publish_missing(now: datetime) -> None:
    """No publish_date → ingestion_date is the only signal. Some RSS
    feeds (especially X via RSSHub) drop the publish field on rare
    items; the helper must not crash and should anchor on ingestion."""
    ingest = now - timedelta(hours=2)
    first, last = compute_event_seen_window([(None, ingest)], at=now)
    assert first == ingest
    assert last == ingest


def test_min_across_cluster_for_first_seen(now: datetime) -> None:
    publish_old = now - timedelta(hours=20)
    publish_new = now - timedelta(hours=2)
    ingest = now - timedelta(hours=1)
    first, last = compute_event_seen_window(
        [(publish_old, ingest), (publish_new, ingest)],
        at=now,
    )
    assert first == publish_old
    assert last == publish_new


def test_last_seen_is_oldest_known_timestamp_per_article(now: datetime) -> None:
    """Critical regression test for the user-reported bug.

    A cluster of one X tweet: publish_date = 17h ago, ingestion = 1h ago.
    Pre-fix, `last_seen = max(publish_date OR ingestion_date)` → since
    `or` short-circuits to publish_date when truthy → ok here.

    But the REAL prod bug was the fast-path NOT calling any helper at
    all and falling to `server_default=NOW()`. This test pins the
    helper's contract: a 17h-old tweet must produce `last_seen = 17h ago`,
    not now.
    """
    publish = now - timedelta(hours=17)
    ingest = now - timedelta(hours=1)
    first, last = compute_event_seen_window([(publish, ingest)], at=now)
    assert (now - last) >= timedelta(hours=16)
    assert (now - last) <= timedelta(hours=17, minutes=1)


def test_handles_articles_with_no_timestamps_at_all(now: datetime) -> None:
    """An article missing both publish_date and ingestion_date should
    not contribute. If ALL articles lack timestamps, fall back to now."""
    first, last = compute_event_seen_window(
        [(None, None), (None, None)],
        at=now,
    )
    assert first == now
    assert last == now


def test_mixed_complete_and_incomplete_articles(now: datetime) -> None:
    """One article has both timestamps, one has neither.
    The cluster's window must reflect the dated article only."""
    publish = now - timedelta(hours=5)
    ingest = now - timedelta(hours=4)
    first, last = compute_event_seen_window(
        [(publish, ingest), (None, None)],
        at=now,
    )
    assert first == publish
    assert last == publish
