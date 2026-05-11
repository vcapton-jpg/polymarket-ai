"""Freshness helpers — single place for content-age rules (real-time pipeline)."""

from datetime import UTC, datetime, timedelta


def now_utc() -> datetime:
    return datetime.now(UTC)


def content_reference_time(
    publish_date: datetime | None,
    ingestion_date: datetime | None,
) -> datetime | None:
    """Oldest known timestamp for the story (conservative staleness).

    If both exist, use min so undated clock skew does not extend apparent freshness.
    """
    if publish_date is not None and ingestion_date is not None:
        return min(publish_date, ingestion_date)
    return publish_date or ingestion_date


def is_fresh_enough(
    publish_date: datetime | None,
    ingestion_date: datetime | None,
    *,
    max_age_hours: float,
    at: datetime | None = None,
) -> bool:
    """True if the item is not older than max_age_hours by reference time."""
    ref = content_reference_time(publish_date, ingestion_date)
    if ref is None:
        return True
    t = at or now_utc()
    return (t - ref) <= timedelta(hours=max_age_hours)


def signal_event_still_fresh(
    last_seen: datetime,
    *,
    max_age_hours: float,
    at: datetime | None = None,
) -> bool:
    """Events older than this should not open new scoring work."""
    t = at or now_utc()
    return (t - last_seen) <= timedelta(hours=max_age_hours)


def compute_event_seen_window(
    article_dates: list[tuple[datetime | None, datetime | None]],
    *,
    at: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Derive (first_seen, last_seen) for an event cluster.

    Each cluster article contributes a `content_reference_time` (the
    older of publish_date and ingestion_date — conservative against
    clock-skew that would extend apparent freshness). The window is
    `(min, max)` over those references.

    If no article has any usable timestamp, fall back to `at` (default
    now()) for both bounds — safe degenerate value, never None.

    Single source of truth for the batch path (`event_builder.py`) AND
    the fast path (`tasks_pipeline._try_instant_event_async`). The
    fast path previously omitted these fields, letting the DB
    `server_default=NOW()` create the appearance of fresh events even
    when their underlying articles were 17 h old. Forcing both paths
    through this helper is the regression-net.
    """
    fallback = at or now_utc()
    refs: list[datetime] = []
    for publish_date, ingestion_date in article_dates:
        ref = content_reference_time(publish_date, ingestion_date)
        if ref is not None:
            refs.append(ref)
    if not refs:
        return fallback, fallback
    return min(refs), max(refs)
