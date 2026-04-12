"""Simple clustering for event detection."""

import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Default clustering parameters
DEFAULT_COSINE_THRESHOLD = 0.82
DEFAULT_TIME_WINDOW_MINUTES = 60


class SimpleClusterer:
    """Simple clustering for news articles into events."""

    def __init__(
        self,
        cosine_threshold: float = DEFAULT_COSINE_THRESHOLD,
        time_window_minutes: int = DEFAULT_TIME_WINDOW_MINUTES,
    ):
        """Initialize the clusterer.

        Args:
            cosine_threshold: Cosine similarity threshold for clustering.
            time_window_minutes: Time window for clustering.
        """
        self.cosine_threshold = cosine_threshold
        self.time_window_minutes = time_window_minutes

    def is_within_time_window(
        self,
        date1: Optional[datetime],
        date2: datetime,
    ) -> bool:
        """Check if two dates are within the time window.

        Args:
            date1: First date (can be None).
            date2: Second date.

        Returns:
            True if within time window.
        """
        if date1 is None:
            return False

        delta = abs((date2 - date1).total_seconds() / 60)
        return delta <= self.time_window_minutes

    def find_similar_articles(
        self,
        target_embedding: list[float],
        candidate_embeddings: list[list[float]],
        candidate_dates: list[datetime],
        reference_date: datetime,
    ) -> list[int]:
        """Find articles similar to target within time window.

        Args:
            target_embedding: Target article embedding.
            candidate_embeddings: List of candidate embeddings.
            candidate_dates: List of candidate dates.
            reference_date: Reference date for time window.

        Returns:
            List of indices of similar articles.
        """
        similar_indices = []

        if not candidate_embeddings:
            return similar_indices

        target = np.array(target_embedding).reshape(1, -1)
        candidates = np.array(candidate_embeddings)

        # Compute cosine similarity
        similarities = cosine_similarity(target, candidates)[0]

        for i, (sim, date) in enumerate(zip(similarities, candidate_dates)):
            if sim >= self.cosine_threshold and self.is_within_time_window(
                date, reference_date
            ):
                similar_indices.append(i)

        return similar_indices

    def cluster_articles(
        self,
        articles: list[dict],
    ) -> list[list[dict]]:
        """Cluster articles into events.

        Args:
            articles: List of article dictionaries with embeddings.

        Returns:
            List of clusters, each cluster is a list of articles.
        """
        if not articles:
            return []

        # Sort by date
        sorted_articles = sorted(
            articles,
            key=lambda a: a.get("ingestion_date", datetime.utcnow()),
        )

        clusters = []
        used_indices = set()

        for i, article in enumerate(sorted_articles):
            if i in used_indices:
                continue

            embedding = article.get("embedding")
            if not embedding:
                continue

            cluster = [article]
            used_indices.add(i)

            # Find similar articles
            target_date = article.get("ingestion_date", datetime.utcnow())
            candidate_embeddings = []
            candidate_dates = []
            candidate_articles = []

            for j, other in enumerate(sorted_articles):
                if j in used_indices:
                    continue
                if other.get("embedding"):
                    candidate_embeddings.append(other["embedding"])
                    candidate_dates.append(other.get("ingestion_date", datetime.utcnow()))
                    candidate_articles.append(other)

            if candidate_embeddings:
                similar = self.find_similar_articles(
                    embedding,
                    candidate_embeddings,
                    candidate_dates,
                    target_date,
                )

                for idx in similar:
                    cluster.append(candidate_articles[idx])
                    used_indices.add(idx)

            clusters.append(cluster)

        logger.info(f"Created {len(clusters)} clusters from {len(articles)} articles")
        return clusters


def create_simple_clusterer() -> SimpleClusterer:
    """Create a simple clusterer instance.

    Returns:
        Configured SimpleClusterer.
    """
    return SimpleClusterer(
        cosine_threshold=settings.clustering_cosine_threshold,
        time_window_minutes=settings.clustering_time_window_minutes,
    )