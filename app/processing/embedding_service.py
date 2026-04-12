"""Embedding service using OpenAI."""

import json
import logging
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Embedding model
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

# Batch size for embedding computation
BATCH_SIZE = 100


class EmbeddingService:
    """Service for computing text embeddings using OpenAI."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the embedding service.

        Args:
            api_key: OpenAI API key. Uses setting if not provided.
        """
        self._client = AsyncOpenAI(
            api_key=api_key or settings.openai_api_key,
        )
        self._embedding_cache: dict[str, list[float]] = {}

    async def compute_embedding(self, text: str) -> Optional[list[float]]:
        """Compute embedding for a single text.

        Args:
            text: Input text.

        Returns:
            Embedding vector or None.
        """
        if not text:
            return None

        # Check cache
        cache_key = text[:100]  # Use truncated text as cache key
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]

        try:
            response = await self._client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text,
                dimensions=EMBEDDING_DIMENSIONS,
            )

            embedding = response.data[0].embedding

            # Cache the result
            self._embedding_cache[cache_key] = embedding

            return embedding

        except Exception as e:
            logger.error(f"Error computing embedding: {e}")
            return None

    async def compute_embeddings_batch(
        self,
        texts: list[str],
    ) -> list[Optional[list[float]]]:
        """Compute embeddings for multiple texts.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        # Filter and cache existing embeddings
        results = []
        texts_to_compute = []

        for text in texts:
            if not text:
                results.append(None)
                continue

            cache_key = text[:100]
            if cache_key in self._embedding_cache:
                results.append(self._embedding_cache[cache_key])
            else:
                results.append(None)
                texts_to_compute.append(text)

        if not texts_to_compute:
            return results

        # Compute in batches
        all_embeddings = []

        for i in range(0, len(texts_to_compute), BATCH_SIZE):
            batch = texts_to_compute[i : i + BATCH_SIZE]

            try:
                response = await self._client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=batch,
                    dimensions=EMBEDDING_DIMENSIONS,
                )

                for j, data in enumerate(response.data):
                    embedding = data.embedding
                    # Cache each embedding
                    original_text = texts_to_compute[i + j]
                    cache_key = original_text[:100]
                    self._embedding_cache[cache_key] = embedding
                    all_embeddings.append(embedding)

            except Exception as e:
                logger.error(f"Error computing batch embeddings: {e}")
                # Add None for failed embeddings
                all_embeddings.extend([None] * len(batch))

        # Merge results
        final_results = []
        embedding_idx = 0

        for i, result in enumerate(results):
            if result is None:
                if embedding_idx < len(all_embeddings):
                    final_results.append(all_embeddings[embedding_idx])
                    embedding_idx += 1
                else:
                    final_results.append(None)
            else:
                final_results.append(result)

        return final_results

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._embedding_cache.clear()


# Global service instance
_embedding_service: Optional[EmbeddingService] = None


def create_embedding_service() -> EmbeddingService:
    """Create an embedding service instance.

    Returns:
        Configured EmbeddingService.
    """
    return EmbeddingService()


async def get_embedding(text: str) -> Optional[list[float]]:
    """Get embedding for text using global service.

    Args:
        text: Input text.

    Returns:
        Embedding vector.
    """
    global _embedding_service

    if _embedding_service is None:
        _embedding_service = create_embedding_service()

    return await _embedding_service.compute_embedding(text)


async def get_embeddings(texts: list[str]) -> list[Optional[list[float]]]:
    """Get embeddings for multiple texts.

    Args:
        texts: List of input texts.

    Returns:
        List of embedding vectors.
    """
    global _embedding_service

    if _embedding_service is None:
        _embedding_service = create_embedding_service()

    return await _embedding_service.compute_embeddings_batch(texts)