"""BM25 index for text retrieval."""

import logging
from typing import Optional

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class BM25Index:
    """BM25 in-memory index for text search."""

    def __init__(self):
        """Initialize the BM25 index."""
        self._index: Optional[BM25Okapi] = None
        self._documents: list[dict] = []
        self._doc_texts: list[str] = []

    def build_index(self, documents: list[dict], text_field: str = "retrieval_text") -> None:
        """Build the BM25 index.

        Args:
            documents: List of document dictionaries.
            text_field: Field name containing text.
        """
        self._documents = documents
        self._doc_texts = [
            doc.get(text_field, "").split() if doc.get(text_field) else []
            for doc in documents
        ]
        self._index = BM25Okapi(self._doc_texts)
        logger.info(f"Built BM25 index with {len(documents)} documents")

    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict]:
        """Search the index.

        Args:
            query: Search query.
            limit: Maximum results.

        Returns:
            List of document dictionaries with scores.
        """
        if not self._index:
            return []

        query_tokens = query.split()
        scores = self._index.get_scores(query_tokens)

        # Get top documents
        top_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True,
        )[:limit]

        results = []
        for rank, idx in enumerate(top_indices, 1):
            doc = self._documents[idx].copy()
            doc["bm25_score"] = scores[idx]
            doc["bm25_rank"] = rank
            results.append(doc)

        return results


def create_bm25_index() -> BM25Index:
    """Create a BM25 index instance.

    Returns:
        Configured BM25Index.
    """
    return BM25Index()