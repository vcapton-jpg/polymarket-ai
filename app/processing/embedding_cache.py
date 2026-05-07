"""Redis-backed cache for OpenAI embeddings.

Keyed on `sha256(model + ":" + text)` so a model swap (or text change of
even one character) gets a fresh embedding. Stored as a JSON-encoded list
of 1536 floats — ~12-15 KB per entry. With our typical pool of distinct
texts (events ~9 k, news_clean ~9 k, market_retrieval_text ~50 k = ~70 k
unique texts at steady state), a fully populated cache is < 1 GB; the
Redis cap is 1 GB with `noeviction` so we monitor and bump if needed.

TTL is 7 days. Embeddings are deterministic for a given (model, text)
pair so the only reasons to expire are:
  1. Model upgrade (handled by the key including the model name).
  2. Disk pressure on Redis (forces an eviction-policy review).
  3. Bug protection — if we ship a bad embedding, it ages out within a
     week without manual intervention.

Failure mode: cache miss (read fail OR write fail) silently falls back
to the OpenAI call. The cache is purely an optimisation — losing it
degrades performance back to baseline but never breaks correctness. All
Redis exceptions are swallowed and logged at WARNING level.

Audit context (2026-05-06): same event re-scored 9× / h via the rescore
loop, each pass hitting OpenAI for the event embedding (~250 ms p50,
$0.02/M tokens). 60 % cache hit assumption → ~270 s/h reclaimed scoring
worker capacity + ~5 200 fewer embedding calls/day.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 7 days: long enough that re-scores within signal_event_max_age_hours
# (2 h) always hit, but short enough that a model swap rolls through.
_TTL_SECONDS = 60 * 60 * 24 * 7
_NAMESPACE = "embcache"


def _key(model: str, text: str) -> str:
    digest = hashlib.sha256(f"{model}:{text}".encode("utf-8")).hexdigest()
    return f"{_NAMESPACE}:{digest}"


_client = None  # populated lazily — avoids importing redis at module-load


def _get_client():
    """Lazy redis client — async, single-connection, no pool needed since
    embedding cache calls are one-shot GET/SET. If the import or the
    connection fails the caller falls through to the OpenAI path."""
    global _client
    if _client is not None:
        return _client
    try:
        import redis.asyncio as aioredis  # type: ignore[import-not-found]

        settings = get_settings()
        _client = aioredis.from_url(settings.redis_url, decode_responses=True)
        return _client
    except Exception as e:
        logger.warning("embedding_cache: redis client init failed: %s", e)
        return None


async def get_cached(model: str, text: str) -> Optional[list[float]]:
    """Return the cached embedding for (model, text) or None on miss/error."""
    if not text or not text.strip():
        return None
    client = _get_client()
    if client is None:
        return None
    try:
        raw = await client.get(_key(model, text))
        if raw is None:
            return None
        # decode_responses=True → str; parse the JSON list of floats.
        return json.loads(raw)
    except Exception as e:
        # Cache miss is normal; only log truly anomalous errors. We use
        # debug to avoid log noise on a flaky redis blip — the OpenAI
        # path always backstops correctness.
        logger.debug("embedding_cache GET failed: %s", e)
        return None


async def set_cached(model: str, text: str, embedding: list[float]) -> None:
    """Best-effort write. Failures are silent — cache is opportunistic."""
    if not text or not text.strip() or not embedding:
        return
    client = _get_client()
    if client is None:
        return
    try:
        await client.setex(
            _key(model, text),
            _TTL_SECONDS,
            json.dumps(embedding),
        )
    except Exception as e:
        logger.debug("embedding_cache SET failed: %s", e)
