"""Event builder — creates Event rows from article clusters."""

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from app.db.models import Event, EventNewsLink

logger = logging.getLogger(__name__)


def build_event_from_cluster(
    articles: list[dict],
) -> tuple[Event, list[int]]:
    """Build an Event from a cluster of news_clean dicts.

    Each dict must have:
        clean_id, title, clean_text, bucket, source_name,
        publish_date (or ingestion_date), entities (list[dict])

    Returns (Event instance, list of clean_ids for EventNewsLink).
    """
    if not articles:
        raise ValueError("Empty cluster")

    primary = max(
        articles,
        key=lambda a: a.get("publish_date") or a.get("ingestion_date") or datetime.min,
    )

    event_title = primary.get("title", "Untitled Event")

    texts = [a.get("clean_text", "")[:300] for a in articles]
    event_summary = " | ".join(texts)[:600]

    all_entities: list[str] = []
    for a in articles:
        for ent in a.get("entities", []):
            all_entities.append(ent.get("entity_value", ""))
    key_entities = [e for e, _ in Counter(all_entities).most_common(10) if e]

    buckets = [a.get("bucket") for a in articles if a.get("bucket")]
    bucket = Counter(buckets).most_common(1)[0][0] if buckets else "other"

    sources = {a.get("source_name") for a in articles if a.get("source_name")}

    dates = [
        a.get("publish_date") or a.get("ingestion_date")
        for a in articles
        if a.get("publish_date") or a.get("ingestion_date")
    ]
    first_seen = min(dates) if dates else datetime.now(timezone.utc)
    last_seen = max(dates) if dates else datetime.now(timezone.utc)

    retrieval_parts = [event_title, event_summary[:300]]
    retrieval_parts.extend(key_entities[:5])
    event_retrieval_text = " ".join(retrieval_parts)

    event = Event(
        event_title=event_title,
        event_summary=event_summary,
        event_retrieval_text=event_retrieval_text,
        key_entities=key_entities,
        event_type=None,
        bucket=bucket,
        articles_count=len(articles),
        unique_sources_count=len(sources),
        first_seen=first_seen,
        last_seen=last_seen,
        processing_status="pending",
    )

    clean_ids = [a["clean_id"] for a in articles if a.get("clean_id")]
    return event, clean_ids
