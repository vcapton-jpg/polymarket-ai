"""Celery task: shadow-rerun the sourcing step for a newly-persisted signal.

Chantier #2. The task is idempotent, rate-limited, and killable via
`SOURCING_SHADOW_ENABLED`. Task 9 ships the skeleton (kill-switch +
idempotency gate); Task 10 adds the pool-fetch + re-rank + LLM-rerun body.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.db.database import get_session_factory
from app.db.models import SignalPrediction
from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


SHADOW_VARIANT = "signal_v2_reranked"


@celery_app.task(
    name="app.workers.tasks_sourcing.sourcing_shadow_rerun",
    bind=True,
    rate_limit="30/m",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def sourcing_shadow_rerun(self, signal_id: int) -> None:
    """Re-rank the article pool for `signal_id` and persist the shadow variant.

    Exits early (silently) on any of: kill-switch off, signal missing,
    idempotency hit, empty article pool. Other errors retry up to 3x with
    exponential backoff (30s, 60s, 120s).
    """
    try:
        return _run_async(_run_shadow(signal_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("sourcing_shadow_rerun failed signal_id=%s: %s", signal_id, exc)
        raise self.retry(exc=exc)


async def _run_shadow(signal_id: int) -> None:
    settings = get_settings()
    if not settings.sourcing_shadow_enabled:
        logger.debug("sourcing_shadow_rerun: killed by flag signal_id=%s", signal_id)
        return

    factory = get_session_factory()
    async with factory() as s:
        existing = (await s.execute(
            select(SignalPrediction).where(
                SignalPrediction.signal_id == signal_id,
                SignalPrediction.variant == SHADOW_VARIANT,
            )
        )).scalar_one_or_none()
        if existing is not None:
            logger.debug("sourcing_shadow_rerun: idempotent skip signal_id=%s", signal_id)
            return

        # TASK 10 will add: load Signal/Market -> fetch pool -> rank -> re-call
        # reasoning_analyzer -> persist SignalPrediction + SignalArticle rows.
        # For now the skeleton is a no-op beyond the gates.
        return
