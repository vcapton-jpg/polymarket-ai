"""Freshness helpers — single place for content-age rules (real-time pipeline)."""

from datetime import datetime, timedelta, timezone
from typing import Optional


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def content_reference_time(
    publish_date: Optional[datetime],
    ingestion_date: Optional[datetime],
) -> Optional[datetime]:
    """Oldest known timestamp for the story (conservative staleness).

    If both exist, use min so undated clock skew does not extend apparent freshness.
    """
    if publish_date is not None and ingestion_date is not None:
        return min(publish_date, ingestion_date)
    return publish_date or ingestion_date


def is_fresh_enough(
    publish_date: Optional[datetime],
    ingestion_date: Optional[datetime],
    *,
    max_age_hours: float,
    at: Optional[datetime] = None,
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
    at: Optional[datetime] = None,
) -> bool:
    """Events older than this should not open new scoring work."""
    t = at or now_utc()
    return (t - last_seen) <= timedelta(hours=max_age_hours)
