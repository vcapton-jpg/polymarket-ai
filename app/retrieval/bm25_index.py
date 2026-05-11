"""BM25 index for text retrieval with proper tokenisation."""

import logging
import re

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)

_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "can", "could", "of", "in", "to", "for",
    "with", "on", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "and", "but", "or", "nor", "not", "so", "yet",
    "both", "either", "neither", "each", "every", "all", "any", "few",
    "more", "most", "other", "some", "such", "no", "only", "own", "same",
    "than", "too", "very", "just", "because", "if", "when", "where",
    "how", "what", "which", "who", "whom", "this", "that", "these",
    "those", "it", "its", "he", "she", "they", "them", "we", "us",
    "i", "me", "my", "your", "his", "her", "our", "their",
})


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, remove stop words."""
    if not text:
        return []
    text = _PUNCT_RE.sub(" ", text.lower())
    return [tok for tok in text.split() if tok and tok not in _STOP_WORDS]


class BM25Index:
    """BM25 in-memory index for text search."""

    def __init__(self):
        self._index: BM25Okapi | None = None
        self._documents: list[dict] = []

    def build_index(self, documents: list[dict], text_field: str = "retrieval_text") -> None:
        self._documents = documents
        tokenized = [
            _tokenize(doc.get(text_field, "")) for doc in documents
        ]
        self._index = BM25Okapi(tokenized)
        logger.info("Built BM25 index with %d documents", len(documents))

    def search(self, query: str, limit: int = 10) -> list[dict]:
        if not self._index:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores = self._index.get_scores(query_tokens)

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
    return BM25Index()
