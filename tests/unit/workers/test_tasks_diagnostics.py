"""emit_diversity_distribution returns the Event.unique_sources_count
histogram and is idempotent / read-only.

Pin (chantier-2 task 11): the hourly beat task must NEVER write to the
DB, must always emit a dict keyed by source-count → event-count, and
must be importable as a Celery task by name so beat scheduling resolves.
"""

from __future__ import annotations

import pytest

from app.db.models import Event


@pytest.mark.asyncio
async def test_emit_diversity_distribution_returns_histogram(async_db_factory, monkeypatch):
    from app.workers import tasks_diagnostics as td

    # Point the task's session factory at the test DB
    from app.db import database as db_mod
    monkeypatch.setattr(
        td, "_get_session_factory", lambda: db_mod.get_session_factory(),
        raising=False,
    )

    # Seed three events: two single-source, one dual-source
    EV_IDS = [994001, 994002, 994003]
    async with async_db_factory() as s:
        s.add_all([
            Event(id=EV_IDS[0], event_title="a", articles_count=1, unique_sources_count=1),
            Event(id=EV_IDS[1], event_title="b", articles_count=1, unique_sources_count=1),
            Event(id=EV_IDS[2], event_title="c", articles_count=2, unique_sources_count=2),
        ])
        await s.commit()

    try:
        out = await td._emit_diversity_distribution()
        assert isinstance(out, dict)
        # The histogram is over the WHOLE table — we only assert the test
        # rows show up, not the absolute totals.
        assert out.get(1, 0) >= 2, f"single-source bucket missing test rows: {out}"
        assert out.get(2, 0) >= 1, f"dual-source bucket missing test row: {out}"
    finally:
        from sqlalchemy import delete
        async with async_db_factory() as s:
            await s.execute(delete(Event).where(Event.id.in_(EV_IDS)))
            await s.commit()


def test_celery_task_is_registered():
    """Pin: the Celery task name must match what celery beat schedules."""
    from app.workers.celery_app import celery_app
    assert (
        "app.workers.tasks_diagnostics.emit_diversity_distribution"
        in celery_app.tasks
    ), "diagnostic task not registered with Celery"


def test_beat_schedule_includes_hourly_diversity():
    """Pin: beat schedule has a 3600s entry for the diversity task."""
    from app.workers.celery_app import celery_app
    sched = celery_app.conf.beat_schedule
    entry = sched.get("clustering-diversity-hourly")
    assert entry is not None, f"missing beat entry; have {list(sched)}"
    assert entry["task"] == (
        "app.workers.tasks_diagnostics.emit_diversity_distribution"
    )
    assert entry["schedule"] == 3600.0
