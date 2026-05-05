"""Embedding service — OpenAI text-embedding-3-small with batch support."""

import logging
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

DIMENSIONS = 1536


OPENAI_TIMEOUT_SECONDS = 30.0


class EmbeddingService:
    def __init__(self):
        # Explicit 30 s timeout on OpenAI calls. The SDK default is 600 s;
        # without a ceiling, a hung TCP socket sits on a Celery worker
        # thread for 10 minutes, blows past `task_time_limit=600 s`, and
        # forces a worker SIGKILL. That's the silent crash loop diagnosed
        # 2026-05-04. Embedding p50 ~80 ms, p99 ~3 s — 30 s covers the
        # network tail comfortably while bounding the worst case.
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=OPENAI_TIMEOUT_SECONDS,
        )
        self._model = settings.openai_embedding_model

    async def compute_single(self, text: str) -> Optional[list[float]]:
        if not text or not text.strip():
            return None
        try:
            resp = await self._client.embeddings.create(
                model=self._model,
                input=text,
                dimensions=DIMENSIONS,
            )
            return resp.data[0].embedding
        except Exception as e:
            logger.error("Embedding error: %s", e)
            return None

    async def compute_batch(self, texts: list[str]) -> list[Optional[list[float]]]:
        if not texts:
            return []

        results: list[Optional[list[float]]] = [None] * len(texts)
        valid_indices = [i for i, t in enumerate(texts) if t and t.strip()]

        batch_size = settings.embedding_batch_size
        for start in range(0, len(valid_indices), batch_size):
            chunk_indices = valid_indices[start : start + batch_size]
            chunk_texts = [texts[i] for i in chunk_indices]

            try:
                resp = await self._client.embeddings.create(
                    model=self._model,
                    input=chunk_texts,
                    dimensions=DIMENSIONS,
                )
                for j, datum in enumerate(resp.data):
                    results[chunk_indices[j]] = datum.embedding
            except Exception as e:
                logger.error("Batch embedding error (chunk %d): %s", start, e)

        return results


_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _service
    if _service is None:
        _service = EmbeddingService()
    return _service


async def get_embedding(text: str) -> Optional[list[float]]:
    return await get_embedding_service().compute_single(text)


async def get_embeddings(texts: list[str]) -> list[Optional[list[float]]]:
    return await get_embedding_service().compute_batch(texts)
