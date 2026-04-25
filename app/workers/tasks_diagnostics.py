"""Diversity-distribution diagnostic, run hourly via Celery beat.

Logs the same numbers as `scripts/clustering_diagnostic.py` so we can
watch the impact of clustering changes ratchet over time. Read-only —
no DB writes, no external calls.

Wired into beat in `app/workers/celery_app.py` under the schedule key
``clustering-diversity-hourly``.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select

from app.db.database import get_session_factory
from app.db.models import Event
from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_session_factory():
    """Indirection so tests can swap in a test-DB factory."""
    return get_session_factory()


async def _emit_diversity_distribution() -> dict[int, int]:
    session_factory = _get_session_factory()
    async with session_factory() as s:
        rows = (
            await s.execute(
                select(Event.unique_sources_count, func.count(Event.id))
                .group_by(Event.unique_sources_count)
                .order_by(Event.unique_sources_count)
            )
        ).all()
    distribution = {int(v or 0): int(c) for v, c in rows}
    total = sum(distribution.values()) or 1
    pct = {k: round(100 * v / total, 1) for k, v in distribution.items()}
    logger.info(
        "clustering.diversity total=%d distribution=%s pct=%s",
        total,
        distribution,
        pct,
    )
    return distribution


@celery_app.task(name="app.workers.tasks_diagnostics.emit_diversity_distribution")
def emit_diversity_distribution() -> dict[int, int]:
    return _run_async(_emit_diversity_distribution())
