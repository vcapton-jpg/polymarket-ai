"""Event builder for creating events from news clusters."""

import json
import logging
from datetime import datetime
from typing import Optional

from app.db.models import Event, EventNewsLink
from app.processing.bucket_classifier import create_bucket_classifier

logger = logging.getLogger(__name__)


class EventBuilder:
    """Builder for creating events from news clusters."""

    def __init__(self):
        """Initialize the event builder."""
        self.bucket_classifier = create_bucket_classifier()

    def build_event_retrieval_text(
        self,
        title: str,
        summary: Optional[str],
        key_entities: dict,
    ) -> str:
        """Build retrieval text for an event.

        Args:
            title: Event title.
            summary: Event summary.
            key_entities: Key entities extracted from news.

        Returns:
            Retrieval text.
        """
        parts = [title]

        if summary:
            parts.append(summary)

        # Add key entities
        if key_entities:
            for entity_type, entities in key_entities.items():
                if entities:
                    parts.extend(entities[:3])  # Add top 3 per type

        return " ".join(parts)

    def determine_bucket(self, title: str, content: str) -> str:
        """Determine the topic bucket.

        Args:
            title: Article title.
            content: Article content.

        Returns:
            Topic bucket.
        """
        text = f"{title} {content[:500]}"
        return self.bucket_classifier.predict(text)

    async def create_event(
        self,
        cluster: list[dict],
    ) -> Event:
        """Create an event from a cluster of articles.

        Args:
            cluster: List of article dictionaries.

        Returns:
            Created Event instance.
        """
        if not cluster:
            raise ValueError("Cannot create event from empty cluster")

        # Get primary article (most recent)
        primary = max(cluster, key=lambda a: a.get("ingestion_date", datetime.min))

        # Build title from primary article
        title = primary.get("title", "Untitled Event")

        # Build summary (first 200 chars of content)
        content = primary.get("content", "")
        summary = content[:200] if content else None

        # Extract key entities
        key_entities = primary.get("key_entities") or {
            "persons": [],
            "locations": [],
            "organizations": [],
            "events": [],
        }

        # Determine bucket
        bucket = self.determine_bucket(title, content)

        # Build retrieval text
        event_retrieval_text = self.build_event_retrieval_text(
            title, summary, key_entities
        )

        # Create event
        event = Event(
            title=title,
            summary=summary,
            key_entities=json.dumps(key_entities),
            bucket=bucket,
            source_count=len(cluster),
            created_at=datetime.utcnow(),
            event_retrieval_text=event_retrieval_text,
            embedding_computed=False,
        )

        return event


def create_event_builder() -> EventBuilder:
    """Create an event builder instance.

    Returns:
        Configured EventBuilder.
    """
    return EventBuilder()