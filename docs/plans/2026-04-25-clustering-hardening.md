# Clustering Hardening Implementation Plan

> **STATUS — 2026-04-25 (post-execution amendment).** Tasks 1-4, 7, 11, 12 shipped. Tasks 5-6 (simhash threshold tightening) and Tasks 8-10 (`min_unique_sources_per_event` gate) **were skipped** after empirical investigation contradicted their premises. See the **Empirical findings** appendix at the bottom of this file for the data, and `docs/specs/2026-04-25-clustering-tuning-followup.md` (chantier #2.5) for the actual lever.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the event clustering pipeline from producing 99% single-source events by fixing three cumulative bugs (over-aggressive simhash dedup, missing diversity gate at event creation, stale `unique_sources_count`).

**Architecture:** Three independent fixes applied in dependency order so each one has the headroom the next needs. Fix the dedup first (so cross-outlet near-duplicates can coexist), recompute counts on every link insert (so the diversity column tells the truth), and only then enforce a `min_unique_sources` gate at event creation (now that diversity actually has room to form).

**Tech Stack:** Python / SQLAlchemy async / Celery / pytest-asyncio. Touches `app/workers/tasks_pipeline.py`, `app/event_engine/event_builder.py`, `app/core/config.py`, plus a backfill script and a beat-scheduled diagnostic.

---

## Context — the three cumulative bugs

Audit 2026-04-25 surfaced that **3145 / 3177 (99.0%)** events in prod have `unique_sources_count = 1`. Three distinct mechanisms compound:

1. **Simhash dedup runs cross-source at a 9-bit Hamming gate (out of 64)** — a Reuters wire collapses every Bloomberg/AP rewrite of the same story, so the cluster never gets a second source. Defined in `app/workers/tasks_pipeline.py:571-594`, threshold `clustering_simhash_threshold=0.15` (`int(64*0.15)=9`).

2. **No `min_unique_sources` gate at event creation** — `min_articles_per_event=1`, so a single wire becomes a published event. Defined in `app/workers/tasks_pipeline.py:250` (fast path) and `:506` (batch path).

3. **`Event.unique_sources_count` is write-once** — set at creation in `app/event_engine/event_builder.py:73-74` and `app/workers/tasks_pipeline.py:293-294`. No code path updates it when a later `EventNewsLink` is added. The API/UI reads the stale column; the scorer recomputes via JOIN (so the penalty is honest) but no other consumer is.

Fix order is **3 → 1 → 2**: bug 3 makes the column trustworthy, bug 1 lets diversity form, bug 2 enforces a quality floor only once headroom exists. Reordering would either erase prod inventory or silently mask the wins.

---

## File Structure

**Modified:**
- `app/core/config.py` — add `min_unique_sources_per_event` setting; lower `clustering_simhash_threshold` default
- `app/workers/tasks_pipeline.py` — call new `recompute_event_counts` helper after link inserts; tighten dedup query and gate
- `app/event_engine/event_builder.py` — call helper at creation time too (replaces the inline initial-set)
- `BLUEPRINT.md` — document the new gate / threshold

**Created:**
- `app/event_engine/event_counts.py` — `recompute_event_counts(session, event_id)` helper
- `scripts/backfill_event_counts.py` — one-shot to repair stale rows
- `scripts/clustering_diagnostic.py` — read-only SQL: distribution of `unique_sources_count` and `articles_count`
- `app/workers/tasks_diagnostics.py` — Celery task wrapping the diagnostic, beat-scheduled hourly
- `tests/integration/test_event_counts_recompute.py`
- `tests/integration/test_simhash_dedup_threshold.py`
- `tests/integration/test_min_unique_sources_gate.py`

---

## Task 1: Baseline diagnostic — capture the bug numerically

**Files:**
- Create: `scripts/clustering_diagnostic.py`

- [ ] **Step 1: Write the script**

```python
"""Print the current distribution of event-cluster diversity.

Read-only — safe to run against prod. Used as a before/after measurement
for the clustering-hardening chantier.

Usage:
    docker compose exec app python -m scripts.clustering_diagnostic
"""

from __future__ import annotations

import asyncio
from sqlalchemy import func, select

from app.db.database import get_session_factory
from app.db.models import Event, EventNewsLink


async def main() -> None:
    session_factory = get_session_factory()
    async with session_factory() as s:
        # Stored column distribution (what the API/UI sees today)
        rows = (await s.execute(
            select(Event.unique_sources_count, func.count(Event.id))
            .group_by(Event.unique_sources_count)
            .order_by(Event.unique_sources_count)
        )).all()
        print("Event.unique_sources_count (STORED):")
        total = sum(c for _, c in rows) or 1
        for v, c in rows:
            print(f"  {v:>3} | {c:>6} ({100*c/total:5.1f}%)")

        # Live recomputed distribution from EventNewsLink (the truth)
        live_subq = (
            select(
                EventNewsLink.event_id,
                func.count(func.distinct(EventNewsLink.clean_id)).label("links"),
            )
            .group_by(EventNewsLink.event_id)
            .subquery()
        )
        live_rows = (await s.execute(
            select(live_subq.c.links, func.count())
            .group_by(live_subq.c.links)
            .order_by(live_subq.c.links)
        )).all()
        print("\nEvent link count (LIVE from event_news_links):")
        total = sum(c for _, c in live_rows) or 1
        for v, c in live_rows:
            print(f"  {v:>3} | {c:>6} ({100*c/total:5.1f}%)")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run it and pin the baseline in the commit message**

Run: `docker compose exec app python -m scripts.clustering_diagnostic`
Expected: a table showing the audit's 3145 / 3177 single-source figure (or whatever it is on the day of execution). Capture the output verbatim — every later task will reference it.

- [ ] **Step 3: Commit**

```bash
git add scripts/clustering_diagnostic.py
git commit -m "chore(clustering): baseline diagnostic for source-diversity audit"
```

---

## Task 2: `recompute_event_counts` helper — write the failing test

**Files:**
- Test: `tests/integration/test_event_counts_recompute.py`

- [ ] **Step 1: Write the failing test**

```python
"""recompute_event_counts(event_id) keeps Event.{articles,unique_sources}_count
in sync with the live event_news_links state.

Pre-fix bug (audit 2026-04-25): both columns are written once at event
creation in event_builder/tasks_pipeline and never updated. Adding a new
EventNewsLink for an existing event leaves the stored counts stale; the
API and signal_mapper read the stale value while the scorer correctly
recomputes from the JOIN.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete

from app.db.models import Event, EventNewsLink, News, NewsClean


@pytest.mark.asyncio
async def test_recompute_updates_counts_after_new_link(async_db_factory):
    from app.event_engine.event_counts import recompute_event_counts

    EVENT_ID = 993100
    URL_BASE = "https://example.com/recompute-"

    async with async_db_factory() as s:
        s.add(Event(
            id=EVENT_ID, event_title="e",
            articles_count=1, unique_sources_count=1,
        ))
        n1 = News(
            url=URL_BASE + "1", title="t1", source_name="reuters",
            source_tier=1, source_weight=0.95,
        )
        n2 = News(
            url=URL_BASE + "2", title="t2", source_name="bloomberg",
            source_tier=1, source_weight=0.95,
        )
        s.add_all([n1, n2])
        await s.flush()
        c1 = NewsClean(news_id=n1.id, clean_text="t1 body")
        c2 = NewsClean(news_id=n2.id, clean_text="t2 body")
        s.add_all([c1, c2])
        await s.flush()
        s.add(EventNewsLink(event_id=EVENT_ID, clean_id=c1.id))
        s.add(EventNewsLink(event_id=EVENT_ID, clean_id=c2.id))
        await s.commit()

    try:
        async with async_db_factory() as s:
            await recompute_event_counts(s, event_id=EVENT_ID)
            await s.commit()

            ev = (await s.get(Event, EVENT_ID))
            assert ev.articles_count == 2, "articles_count not refreshed"
            assert ev.unique_sources_count == 2, (
                "unique_sources_count still stale — recompute_event_counts "
                "did not update Event row from event_news_links JOIN"
            )
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(EventNewsLink).where(EventNewsLink.event_id == EVENT_ID))
            await s.execute(delete(NewsClean).where(NewsClean.news.has(News.url.startswith(URL_BASE))))
            await s.execute(delete(News).where(News.url.startswith(URL_BASE)))
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.commit()


@pytest.mark.asyncio
async def test_recompute_handles_event_with_no_links(async_db_factory):
    """Edge case: event exists but has zero links yet (creation-in-progress).
    Helper must not crash and must clamp counts to >= 1 (the column has a
    NOT NULL default of 1; zero would violate the soft contract that an
    event always represents at least one article)."""
    from app.event_engine.event_counts import recompute_event_counts

    EVENT_ID = 993101
    async with async_db_factory() as s:
        s.add(Event(
            id=EVENT_ID, event_title="orphan",
            articles_count=1, unique_sources_count=1,
        ))
        await s.commit()
    try:
        async with async_db_factory() as s:
            await recompute_event_counts(s, event_id=EVENT_ID)
            await s.commit()
            ev = await s.get(Event, EVENT_ID)
            assert ev.articles_count >= 1
            assert ev.unique_sources_count >= 1
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.commit()
```

- [ ] **Step 2: Run to verify it fails with ImportError**

Run: `docker compose exec app pytest tests/integration/test_event_counts_recompute.py -v`
Expected: `ImportError` or `ModuleNotFoundError: app.event_engine.event_counts` — module does not exist yet.

---

## Task 3: `recompute_event_counts` helper — implementation

**Files:**
- Create: `app/event_engine/event_counts.py`

- [ ] **Step 1: Write the helper**

```python
"""Single source of truth for Event.{articles,unique_sources}_count.

Both columns were originally set at event creation and never updated. The
fix is to recompute from the live `event_news_links` join after every
mutation that adds or removes a link.

Kept in its own module (not on the model class) so that:
  - Both the fast path and the batch path call the same code
  - The backfill script can repair stale rows without going through the
    creation flow
  - It can be unit-tested in isolation against a real session
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.db.models import Event, EventNewsLink, News, NewsClean

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def recompute_event_counts(session: "AsyncSession", *, event_id: int) -> None:
    """Refresh Event.articles_count + Event.unique_sources_count for one event.

    Caller is responsible for the surrounding transaction — this helper
    issues the SELECT + UPDATE on the open session and does NOT commit.

    Counts are clamped to >= 1: an event row implies at least one article
    by construction; a zero count would silently violate that and surface
    as `0 sources` in the UI mid-creation.
    """
    row = (
        await session.execute(
            select(
                func.count(EventNewsLink.id).label("articles"),
                func.count(func.distinct(News.source_name)).label("sources"),
            )
            .select_from(EventNewsLink)
            .join(NewsClean, NewsClean.id == EventNewsLink.clean_id)
            .join(News, News.id == NewsClean.news_id)
            .where(EventNewsLink.event_id == event_id)
        )
    ).one()

    articles = max(1, int(row.articles or 0))
    sources = max(1, int(row.sources or 0))

    ev = await session.get(Event, event_id)
    if ev is None:
        return
    ev.articles_count = articles
    ev.unique_sources_count = sources
```

- [ ] **Step 2: Run the tests — both must pass**

Run: `docker compose exec app pytest tests/integration/test_event_counts_recompute.py -v`
Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add app/event_engine/event_counts.py tests/integration/test_event_counts_recompute.py
git commit -m "feat(event-counts): recompute helper for articles + unique_sources_count"
```

---

## Task 4: Wire `recompute_event_counts` into both event-creation paths

**Files:**
- Modify: `app/event_engine/event_builder.py:73-74` (replace inline counts)
- Modify: `app/workers/tasks_pipeline.py:293-294`, `:302`, `:541` (call after link inserts)
- Test: `tests/integration/test_event_counts_recompute.py` (extend with end-to-end check)

- [ ] **Step 1: Write the failing end-to-end test**

Append to `tests/integration/test_event_counts_recompute.py`:

```python
@pytest.mark.asyncio
async def test_event_builder_uses_recompute(async_db_factory, monkeypatch):
    """Pin the wiring: every event-creation path must go through
    recompute_event_counts so a forgotten manual-update can never silently
    leave counts stale.
    """
    calls: list[int] = []

    from app.event_engine import event_counts as ec_mod

    real = ec_mod.recompute_event_counts

    async def _spy(session, *, event_id: int):
        calls.append(event_id)
        return await real(session, event_id=event_id)

    monkeypatch.setattr(ec_mod, "recompute_event_counts", _spy)

    # Drive the batch event_builder with two articles from two sources.
    EVENT_ID = 993102
    URL_BASE = "https://example.com/eb-recompute-"

    from app.event_engine.event_builder import build_and_persist_event
    from sqlalchemy import delete as sql_delete

    async with async_db_factory() as s:
        n1 = News(
            url=URL_BASE + "1", title="t1", source_name="reuters",
            source_tier=1, source_weight=0.95,
        )
        n2 = News(
            url=URL_BASE + "2", title="t2", source_name="ap",
            source_tier=1, source_weight=0.95,
        )
        s.add_all([n1, n2])
        await s.flush()
        c1 = NewsClean(news_id=n1.id, clean_text="t1 body")
        c2 = NewsClean(news_id=n2.id, clean_text="t2 body")
        s.add_all([c1, c2])
        await s.commit()
        clean_ids = (c1.id, c2.id)

    try:
        async with async_db_factory() as s:
            ev_id = await build_and_persist_event(
                s, clean_ids=list(clean_ids), event_id_override=EVENT_ID,
            )
            await s.commit()
        assert ev_id == EVENT_ID
        assert EVENT_ID in calls, "event_builder did not call recompute_event_counts"
    finally:
        async with async_db_factory() as s:
            await s.execute(sql_delete(EventNewsLink).where(EventNewsLink.event_id == EVENT_ID))
            await s.execute(sql_delete(NewsClean).where(NewsClean.id.in_(clean_ids)))
            await s.execute(sql_delete(News).where(News.url.startswith(URL_BASE)))
            await s.execute(sql_delete(Event).where(Event.id == EVENT_ID))
            await s.commit()
```

NOTE: `build_and_persist_event` may not exist with that exact signature — read the current `event_builder.py` first and either rename the test target or extract a helper that the test can call deterministically. The point is: every code path that inserts an `EventNewsLink` row must end with a `recompute_event_counts(session, event_id=...)` call.

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec app pytest tests/integration/test_event_counts_recompute.py::test_event_builder_uses_recompute -v`
Expected: FAIL with empty `calls` list — current code sets the columns inline and never calls the helper.

- [ ] **Step 3: Refactor event_builder + tasks_pipeline**

Replace every site that writes `event.articles_count =` / `event.unique_sources_count =` with a call to `recompute_event_counts(session, event_id=event.id)` AFTER the new EventNewsLink rows have been added (and `await session.flush()` so the helper sees them).

In `app/event_engine/event_builder.py:73-74`, the original assignment becomes:

```python
# (drop the inline articles_count / unique_sources_count assignments —
#  recompute_event_counts will fill them in once links are inserted)
```

After the loop that inserts `EventNewsLink` rows, before commit:

```python
await session.flush()
from app.event_engine.event_counts import recompute_event_counts
await recompute_event_counts(session, event_id=event.id)
```

Same change at `app/workers/tasks_pipeline.py:293-294` (drop inline) and after the `s.add(EventNewsLink(...))` blocks at `:302` and `:541`.

- [ ] **Step 4: Run all event-builder tests**

Run: `docker compose exec app pytest tests/integration/test_event_counts_recompute.py tests/unit/event_engine/ tests/integration/test_inline_v2_writes.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add app/event_engine/event_builder.py app/workers/tasks_pipeline.py tests/integration/test_event_counts_recompute.py
git commit -m "fix(event-counts): refresh counts after every link insert"
```

---

## Task 5: Tighten simhash dedup — write the failing tests

**Files:**
- Test: `tests/integration/test_simhash_dedup_threshold.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Pin simhash dedup behaviour after the chantier-2 threshold tightening.

Pre-fix (audit 2026-04-25): clustering_simhash_threshold=0.15 ⇒ 9-bit gate
on a 64-bit hash. That window collapses genuinely-different stories from
genuinely-different outlets, suppressing every Bloomberg / AP rewrite of
a Reuters wire and locking events into single-source clusters.

Post-fix: the gate must be tight enough (≤ 4 bits ≈ 6%) that two distinct
news articles on the same topic produce two NewsClean rows.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete

from app.db.models import News, NewsClean
from app.workers.tasks_pipeline import _check_simhash_dup, _compute_simhash


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


@pytest.mark.asyncio
async def test_distinct_stories_not_deduped(async_db_factory):
    """Two articles, two outlets, same topic but different wording — must
    survive dedup as two NewsClean rows so the event-builder sees two
    sources to cluster.
    """
    URLS = ["https://example.com/sim-distinct-1", "https://example.com/sim-distinct-2"]
    text_a = (
        "Federal Reserve raises interest rates by 25 basis points in "
        "March meeting, citing persistent inflation pressures"
    )
    text_b = (
        "The Fed announced a quarter-point hike Wednesday, bringing "
        "benchmark borrowing costs to a 23-year high amid sticky CPI"
    )
    sh_a, sh_b = _compute_simhash(text_a), _compute_simhash(text_b)
    # Sanity — the two hashes ARE far apart (we're not testing a degenerate case)
    assert _hamming(sh_a, sh_b) > 5, (
        f"test inputs too similar (hamming={_hamming(sh_a, sh_b)}); "
        "rewrite the texts so they differ more"
    )

    async with async_db_factory() as s:
        n_a = News(
            url=URLS[0], title="a", source_name="reuters",
            source_tier=1, source_weight=0.95,
        )
        s.add(n_a)
        await s.flush()
        s.add(NewsClean(news_id=n_a.id, clean_text=text_a, simhash=sh_a))
        await s.commit()

    try:
        async with async_db_factory() as s:
            # Bloomberg writes its own version of the same story
            is_dup = await _check_simhash_dup(s, simhash_val=sh_b)
            assert is_dup is False, (
                "distinct story marked as duplicate — threshold still too "
                "permissive (cross-outlet collision)"
            )
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(NewsClean).where(NewsClean.news.has(News.url.in_(URLS))))
            await s.execute(delete(News).where(News.url.in_(URLS)))
            await s.commit()


@pytest.mark.asyncio
async def test_near_identical_wire_syndication_still_deduped(async_db_factory):
    """A literal copy of a Reuters wire republished under a Bloomberg
    headline must STILL be deduped — wire syndication would otherwise
    inflate unique_sources_count artificially.
    """
    URLS = ["https://example.com/sim-wire-1", "https://example.com/sim-wire-2"]
    text = (
        "WASHINGTON (Reuters) - The U.S. Treasury on Friday imposed "
        "sanctions on three companies linked to alleged sanctions evasion."
    )
    sh = _compute_simhash(text)

    async with async_db_factory() as s:
        n = News(
            url=URLS[0], title="reuters", source_name="reuters",
            source_tier=1, source_weight=0.95,
        )
        s.add(n)
        await s.flush()
        s.add(NewsClean(news_id=n.id, clean_text=text, simhash=sh))
        await s.commit()

    try:
        async with async_db_factory() as s:
            is_dup = await _check_simhash_dup(s, simhash_val=sh)
            assert is_dup is True, (
                "wire syndication leaked through — threshold too tight, "
                "exact-text reposts will inflate source counts"
            )
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(NewsClean).where(NewsClean.news.has(News.url.in_(URLS))))
            await s.execute(delete(News).where(News.url.in_(URLS)))
            await s.commit()
```

- [ ] **Step 2: Run — first test must fail, second must pass**

Run: `docker compose exec app pytest tests/integration/test_simhash_dedup_threshold.py -v`
Expected: `test_distinct_stories_not_deduped` FAILS (current 9-bit gate eats it). `test_near_identical_wire_syndication_still_deduped` PASSES.

---

## Task 6: Tighten simhash dedup — implementation

**Files:**
- Modify: `app/core/config.py:130` (lower default)

- [ ] **Step 1: Lower the default threshold**

In `app/core/config.py`, change:

```python
clustering_simhash_threshold: float = 0.15
```

to:

```python
# Hamming gate as a fraction of the 64-bit simhash. 0.15 ⇒ 9 bits, which
# was wide enough to collapse genuinely-different stories from
# genuinely-different outlets (audit 2026-04-25 — 99% single-source
# events). 0.05 ⇒ max(3, 3) = 3 bits, which is tight enough to keep
# wire syndication deduped while letting independent rewrites survive.
clustering_simhash_threshold: float = 0.05
```

The `max(3, int(64 * threshold))` floor in `_check_simhash_dup` already ensures at least a 3-bit gate, so this is a true tightening, not a relaxation in disguise.

- [ ] **Step 2: Run the tests — both must pass now**

Run: `docker compose exec app pytest tests/integration/test_simhash_dedup_threshold.py -v`
Expected: 2 passed.

- [ ] **Step 3: Re-run the full pipeline test slice**

Run: `docker compose exec app pytest tests/integration/test_inline_v2_writes.py tests/unit/event_engine/ tests/integration/test_event_counts_recompute.py -v`
Expected: green. (No other test should hard-code the 0.15 value.)

- [ ] **Step 4: Commit**

```bash
git add app/core/config.py tests/integration/test_simhash_dedup_threshold.py
git commit -m "fix(simhash): tighten dedup gate from 9 bits to 3 bits"
```

---

## Task 7: Backfill stale event counts

**Files:**
- Create: `scripts/backfill_event_counts.py`

- [ ] **Step 1: Write the backfill script**

```python
"""One-shot backfill: refresh Event.{articles,unique_sources}_count from
the live event_news_links state for every event in the database.

Usage:
    docker compose exec app python -m scripts.backfill_event_counts --dry-run
    docker compose exec app python -m scripts.backfill_event_counts

Idempotent — safe to re-run. Batched per 500 events to keep the
transaction short.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from sqlalchemy import select

from app.db.database import get_session_factory
from app.db.models import Event
from app.event_engine.event_counts import recompute_event_counts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BATCH_SIZE = 500


async def main(dry_run: bool) -> None:
    session_factory = get_session_factory()
    async with session_factory() as s:
        ids = (await s.execute(select(Event.id).order_by(Event.id))).scalars().all()
    logger.info("backfill_event_counts: %d events to process", len(ids))

    changed = 0
    for offset in range(0, len(ids), BATCH_SIZE):
        batch = ids[offset:offset + BATCH_SIZE]
        async with session_factory() as s:
            for event_id in batch:
                ev = await s.get(Event, event_id)
                if ev is None:
                    continue
                before = (ev.articles_count, ev.unique_sources_count)
                await recompute_event_counts(s, event_id=event_id)
                after = (ev.articles_count, ev.unique_sources_count)
                if before != after:
                    changed += 1
                    logger.info(
                        "event %s: (a=%d s=%d) -> (a=%d s=%d)",
                        event_id, before[0], before[1], after[0], after[1],
                    )
            if dry_run:
                await s.rollback()
            else:
                await s.commit()
        logger.info("processed %d / %d", offset + len(batch), len(ids))
    logger.info("backfill_event_counts: changed=%d dry_run=%s", changed, dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
```

- [ ] **Step 2: Dry-run against the live DB**

Run: `docker compose exec app python -m scripts.backfill_event_counts --dry-run`
Expected: log lines showing the BEFORE/AFTER for events that have stale counts. Eyeball the output to make sure nothing pathological (e.g. clamping to 1 for an event that should have 50 articles).

- [ ] **Step 3: Real run**

Run: `docker compose exec app python -m scripts.backfill_event_counts`
Expected: same line count as dry-run, ending with `changed=N`.

- [ ] **Step 4: Re-run the diagnostic from Task 1**

Run: `docker compose exec app python -m scripts.clustering_diagnostic`
Expected: the STORED column distribution now matches the LIVE link-count distribution exactly.

- [ ] **Step 5: Commit**

```bash
git add scripts/backfill_event_counts.py
git commit -m "chore(event-counts): backfill stale articles/unique_sources_count"
```

---

## Task 8: `min_unique_sources_per_event` config setting

**Files:**
- Modify: `app/core/config.py`

- [ ] **Step 1: Add the setting**

```python
# Minimum DISTINCT source_name values required for a cluster to become an
# event. The legacy gate is `min_articles_per_event=1`, which silently
# created single-source events at 99% of all events (audit 2026-04-25).
# Setting this to 2 enforces multi-source corroboration. The fast path
# (single-article instant event) is exempted via a separate code path —
# see _try_instant_event_async for the staging behaviour.
min_unique_sources_per_event: int = 2
```

Place it next to `min_articles_per_event` so reviewers see the pair together.

- [ ] **Step 2: Smoke-test the settings module**

Run: `docker compose exec app python -c "from app.core.config import get_settings; s = get_settings(); print(s.min_unique_sources_per_event)"`
Expected: `2`

---

## Task 9: Enforce the gate in the batch event-creation path — failing test

**Files:**
- Test: `tests/integration/test_min_unique_sources_gate.py`

- [ ] **Step 1: Write the failing test**

```python
"""Pin the min_unique_sources_per_event gate at the batch event-creation
site (`tasks_pipeline._process_clustering_batch` / `event_builder`).

Pre-fix (audit 2026-04-25): a cluster of 2 articles from the SAME source
became an event because the only gate was `min_articles_per_event=1`.
Post-fix: must be rejected — diversity is the first quality signal.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.db.models import Event, EventNewsLink, News, NewsClean


@pytest.mark.asyncio
async def test_two_articles_same_source_does_not_create_event(async_db_factory):
    from app.event_engine.event_builder import build_and_persist_event

    URLS = ["https://example.com/single-src-1", "https://example.com/single-src-2"]
    async with async_db_factory() as s:
        n1 = News(
            url=URLS[0], title="r1", source_name="reuters",
            source_tier=1, source_weight=0.95,
        )
        n2 = News(
            url=URLS[1], title="r2", source_name="reuters",
            source_tier=1, source_weight=0.95,
        )
        s.add_all([n1, n2])
        await s.flush()
        c1 = NewsClean(news_id=n1.id, clean_text="x")
        c2 = NewsClean(news_id=n2.id, clean_text="y")
        s.add_all([c1, c2])
        await s.commit()
        clean_ids = (c1.id, c2.id)

    try:
        async with async_db_factory() as s:
            ev_id = await build_and_persist_event(s, clean_ids=list(clean_ids))
            await s.commit()
        # Helper must signal rejection (returns None) — diversity gate.
        assert ev_id is None
        # And no Event row should have been created.
        async with async_db_factory() as s:
            link_count = (await s.execute(
                select(EventNewsLink).where(EventNewsLink.clean_id.in_(clean_ids))
            )).all()
            assert link_count == []
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(NewsClean).where(NewsClean.id.in_(clean_ids)))
            await s.execute(delete(News).where(News.url.in_(URLS)))
            await s.commit()


@pytest.mark.asyncio
async def test_two_articles_two_sources_creates_event(async_db_factory):
    """Sanity check the gate doesn't reject the multi-source happy path."""
    from app.event_engine.event_builder import build_and_persist_event

    URLS = ["https://example.com/multi-src-1", "https://example.com/multi-src-2"]
    async with async_db_factory() as s:
        n1 = News(
            url=URLS[0], title="r", source_name="reuters",
            source_tier=1, source_weight=0.95,
        )
        n2 = News(
            url=URLS[1], title="b", source_name="bloomberg",
            source_tier=1, source_weight=0.95,
        )
        s.add_all([n1, n2])
        await s.flush()
        c1 = NewsClean(news_id=n1.id, clean_text="x")
        c2 = NewsClean(news_id=n2.id, clean_text="y")
        s.add_all([c1, c2])
        await s.commit()
        clean_ids = (c1.id, c2.id)

    try:
        async with async_db_factory() as s:
            ev_id = await build_and_persist_event(s, clean_ids=list(clean_ids))
            await s.commit()
            assert ev_id is not None
            ev = await s.get(Event, ev_id)
            assert ev.unique_sources_count == 2
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(EventNewsLink).where(EventNewsLink.event_id == ev_id))
            await s.execute(delete(NewsClean).where(NewsClean.id.in_(clean_ids)))
            await s.execute(delete(News).where(News.url.in_(URLS)))
            await s.execute(delete(Event).where(Event.id == ev_id))
            await s.commit()
```

- [ ] **Step 2: Run — first test must fail, second must pass**

Run: `docker compose exec app pytest tests/integration/test_min_unique_sources_gate.py -v`
Expected: `test_two_articles_same_source_does_not_create_event` FAILS (current code creates the event); `test_two_articles_two_sources_creates_event` PASSES.

---

## Task 10: Enforce the gate — implementation

**Files:**
- Modify: `app/event_engine/event_builder.py` and/or `app/workers/tasks_pipeline.py`

- [ ] **Step 1: Add the gate at the batch path**

Read `app/event_engine/event_builder.py` and locate the function that converts a cluster (list of clean_ids) into an Event. Just before persisting:

```python
from app.core.config import get_settings

settings = get_settings()
distinct_sources = {a.source_name for a in articles if a.source_name}
if len(distinct_sources) < settings.min_unique_sources_per_event:
    logger.info(
        "min_unique_sources gate: cluster_size=%d distinct_sources=%d < %d — skipping",
        len(articles), len(distinct_sources),
        settings.min_unique_sources_per_event,
    )
    return None
```

Same gate in `app/workers/tasks_pipeline.py:506` (after the `min_articles_per_event` check) — but ONLY for the batch path. The fast path (`_try_instant_event_async`) operates on a single article by definition; gating it would disable instant events entirely. Instead:

- [ ] **Step 2: Mark fast-path events as `pending_validation`**

In `app/workers/tasks_pipeline.py:_try_instant_event_async`, set the new event's `processing_status = "pending_multi_source"` (or reuse an existing status — read the code to choose the right value). Downstream consumers must NOT promote a `pending_multi_source` event to a signal until a second source attaches and `recompute_event_counts` (Task 4) lifts `unique_sources_count` to ≥ 2.

The simplest way to enforce this without rewriting the scoring task: in `app/workers/tasks_scoring.py:_run_full_scoring_pipeline`, immediately after loading the event:

```python
if event.unique_sources_count < settings.min_unique_sources_per_event:
    event.processing_status = "skipped_single_source"
    await session.commit()
    return {"status": "single_source_skipped", "event_id": event_id}
```

This is the smallest blast-radius implementation: fast path keeps creating events (so the article doesn't disappear), but signals only fire once a second source corroborates.

- [ ] **Step 3: Run all three test files**

Run: `docker compose exec app pytest tests/integration/test_min_unique_sources_gate.py tests/integration/test_event_counts_recompute.py tests/integration/test_simhash_dedup_threshold.py -v`
Expected: all green.

- [ ] **Step 4: Run the broader pipeline + scoring slice**

Run: `docker compose exec app pytest tests/unit/event_engine/ tests/unit/scoring/ tests/integration/test_inline_v2_writes.py tests/integration/test_baselines_data_wiring.py -v`
Expected: all green. If something fails, the most likely culprit is a fixture creating a single-source event and expecting it to score — update the fixture to use two sources.

- [ ] **Step 5: Commit**

```bash
git add app/core/config.py app/event_engine/event_builder.py app/workers/tasks_pipeline.py app/workers/tasks_scoring.py tests/integration/test_min_unique_sources_gate.py
git commit -m "feat(clustering): require >= 2 unique sources per scored event"
```

---

## Task 11: Diversity-distribution Celery beat task (observability)

**Files:**
- Create: `app/workers/tasks_diagnostics.py`
- Modify: `app/workers/celery_app.py` (add beat schedule)

- [ ] **Step 1: Write the task**

```python
"""Diversity-distribution diagnostic, run hourly via Celery beat.

Logs the same numbers as scripts/clustering_diagnostic.py so we can watch
the impact of the chantier-2 fixes ratchet up over time. Read-only —
no DB writes, no external calls.
"""

from __future__ import annotations

import logging
from sqlalchemy import func, select

from app.db.models import Event
from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _emit_diversity_distribution() -> dict:
    from app.db.database import get_session_factory
    session_factory = get_session_factory()
    async with session_factory() as s:
        rows = (await s.execute(
            select(Event.unique_sources_count, func.count(Event.id))
            .group_by(Event.unique_sources_count)
            .order_by(Event.unique_sources_count)
        )).all()
    distribution = {int(v or 0): int(c) for v, c in rows}
    total = sum(distribution.values()) or 1
    pct = {k: round(100 * v / total, 1) for k, v in distribution.items()}
    logger.info(
        "clustering.diversity total=%d distribution=%s pct=%s",
        total, distribution, pct,
    )
    return distribution


@celery_app.task(name="app.workers.tasks_diagnostics.emit_diversity_distribution")
def emit_diversity_distribution() -> dict:
    return _run_async(_emit_diversity_distribution())
```

- [ ] **Step 2: Wire into Celery beat**

In `app/workers/celery_app.py` (next to the other diagnostic schedules):

```python
"clustering-diversity-hourly": {
    "task": "app.workers.tasks_diagnostics.emit_diversity_distribution",
    "schedule": 3600.0,
    "options": {"queue": "default"},
},
```

- [ ] **Step 3: Smoke-test the task synchronously**

Run: `docker compose exec app python -c "import asyncio; from app.workers.tasks_diagnostics import _emit_diversity_distribution; print(asyncio.run(_emit_diversity_distribution()))"`
Expected: prints the distribution dict; logger emits the `clustering.diversity` line.

- [ ] **Step 4: Commit**

```bash
git add app/workers/tasks_diagnostics.py app/workers/celery_app.py
git commit -m "feat(observability): hourly clustering-diversity Celery beat"
```

---

## Task 12: BLUEPRINT update + final diagnostic

**Files:**
- Modify: `BLUEPRINT.md`

- [ ] **Step 1: Document the new behaviour**

In the section that describes event clustering (search for `min_articles_per_event` or `clustering_simhash_threshold`), add:

```markdown
### Clustering thresholds (chantier #2 — 2026-04-25)

- `clustering_simhash_threshold: 0.05` (3-bit Hamming gate on 64 bits) —
  tight enough to dedup wire syndication but lets independent rewrites
  from different outlets coexist as separate `news_clean` rows.
- `min_articles_per_event: 1` — fast path can still spawn an event from a
  single article (it stays at `processing_status = "pending_multi_source"`).
- `min_unique_sources_per_event: 2` — only events with at least two
  distinct `source_name` values become signal-eligible. Enforced at
  `_run_full_scoring_pipeline` entry; events below the gate are marked
  `skipped_single_source` and never reach the scorer.
- `Event.unique_sources_count` / `Event.articles_count` — recomputed via
  `app/event_engine/event_counts.recompute_event_counts` after every
  `EventNewsLink` insert; backfill via `scripts/backfill_event_counts.py`.
- Hourly diagnostic: `app.workers.tasks_diagnostics.emit_diversity_distribution`
  logs the `Event.unique_sources_count` histogram.
```

- [ ] **Step 2: Run the diagnostic one last time**

Run: `docker compose exec app python -m scripts.clustering_diagnostic`
Capture the output. The "STORED" and "LIVE" tables should now agree exactly. The single-source share should still be high (we haven't ingested new articles under the new dedup yet) — that's expected. The unlock is forward-looking: every NEW article processed under the new pipeline gets a fair shot at multi-source corroboration.

- [ ] **Step 3: Final commit**

```bash
git add BLUEPRINT.md
git commit -m "docs(blueprint): document chantier-2 clustering thresholds"
```

---

## Self-Review Checklist

After all tasks are merged:

1. **Spec coverage**
   - [ ] Bug 1 (simhash too aggressive) addressed by Task 5–6
   - [ ] Bug 2 (no diversity gate) addressed by Task 8–10
   - [ ] Bug 3 (write-once counts) addressed by Task 2–4 + 7
   - [ ] Observability + measurement covered by Task 1 + 11

2. **Type / signature consistency**
   - [ ] `recompute_event_counts(session, *, event_id: int)` signature is the same in all 4 call sites
   - [ ] `min_unique_sources_per_event` is read via `get_settings()` everywhere (no hard-coded `2`)
   - [ ] `build_and_persist_event` returns `Optional[int]` (event_id or None on rejection)

3. **Placeholder scan**
   - [ ] No `TODO`, `TBD`, or `implement later` comments in committed code
   - [ ] Every test asserts a concrete number (count, hamming, status) — no `assert result is not None`-only tests

4. **Behavioural sanity**
   - [ ] Pre-Task-2 diagnostic output is captured in the Task 1 commit message
   - [ ] Post-Task-7 diagnostic output is captured in the Task 7 commit message (proves backfill landed)
   - [ ] Post-Task-12 diagnostic output is captured in the Task 12 commit message (proves the loop closed)

If any item fails, fix inline. Then invoke `superpowers:finishing-a-development-branch` to wrap.

---

## Empirical findings appendix (2026-04-25)

Investigation during execution falsified two of the plan's three hypotheses. Recorded here so future readers don't re-walk the dead ends.

### Bug 1 (simhash dedup too aggressive) — REJECTED

The plan claimed the 0.15 threshold (max(3, int(64*0.15)) = 9-bit Hamming gate) collapses cross-outlet rewrites. Measured against 800 prod NewsClean rows, comparing the two highest-volume sources (`X: @Reuters` × `X: @FirstSquawk`, 79 × 70 articles):

```
min cross-outlet hamming = 15  (count=1)
                          16  (count=1)
                          ...
                          22  (count=13)   ← mode
                          23  (count=20)   ← mode
                          24  (count=13)
                          25  (count=9)
                          26  (count=4)
```

Not a single cross-outlet pair sat below the 9-bit gate. Lowering to 3 bits would have changed nothing.

**Impact on plan:** Task 5 was repurposed as a characterization test (`tests/integration/test_simhash_dedup_threshold.py`) pinning current behaviour; Task 6 was dropped.

### Bug 3 (write-once counts drift) — REJECTED post-fix

After Task 4 wired `recompute_event_counts` into both creation paths, the backfill ran on 3357 prod events and reported `changed=0`. The "drift" suggested by the original diagnostic was an apples-to-oranges artefact (STORED `unique_sources_count` vs LIVE `count(distinct clean_id)` — different axes). Diagnostic was fixed in Task 7 to compare like with like; once corrected, STORED ≈ LIVE for every event.

**Impact on plan:** Tasks 2-4 + 7 still landed (helper, wiring, backfill, diagnostic) — all useful as forward-looking infrastructure even though there was no historical drift to repair.

### Bug 2 (no min_unique_sources gate) — REAL but UNSAFE TO SHIP AS PLANNED

The 99% single-source-event phenomenon is real, but its cause is upstream of the gate. Cosine similarity measurement against prod embeddings:

```
max-cosine of each Reuters article to ANY FirstSquawk article (n=79):
  p  0 = 0.944
  p  5 = 0.918
  p 10 = 0.637
  p 25 = 0.460
  p 50 = 0.366
  p 75 = 0.307
  p100 = 0.173

>= 0.75 (current cluster threshold): 5 / 79 (6.3%)
>= 0.65                            : 7 / 79 (8.9%)
>= 0.55                            : 12 / 79 (15.2%)
```

Combined with the 120-min `clustering_time_window_minutes`, cross-outlet articles essentially never make it into the same cluster. Multi-article events (1.8% of total) are therefore **same-source repeats**, not corroboration.

**Implication:** Adding `min_unique_sources_per_event=2` would have rejected 97.9% of inventory — every single-source event ever created. Even with the rejection routed to a `pending_multi_source` staging status (as the plan suggested), no further events would ever cross the gate, because the upstream clustering doesn't actually merge cross-outlet articles in the first place.

**Impact on plan:** Tasks 8-10 were dropped. The lever needs to move first: lower `clustering_cosine_threshold` and/or widen `clustering_time_window_minutes`, with empirical sweep against held-out data, before any diversity gate is enforceable. Filed as chantier #2.5 (`docs/specs/2026-04-25-clustering-tuning-followup.md`).

### Net delta shipped

| # | Task | Status | Notes |
|---|---|---|---|
| 1 | Baseline diagnostic | ✅ | Improved in Task 7 (apples-to-apples) |
| 2 | Failing recompute test | ✅ | |
| 3 | recompute helper | ✅ | `app/event_engine/event_counts.py` |
| 4 | Wire helper into both paths | ✅ | Fast + batch |
| 5 | Simhash failing tests | 🔄 | Repurposed as characterization |
| 6 | Tighten simhash threshold | ❌ | Skipped — no-op in prod |
| 7 | Backfill stale counts | ✅ | `changed=0`, infra useful anyway |
| 8 | `min_unique_sources_per_event` setting | ❌ | Skipped — see bug 2 above |
| 9 | Failing gate tests | ❌ | Skipped |
| 10 | Enforce gate at scoring entry | ❌ | Skipped |
| 11 | Hourly diversity beat task | ✅ | `app/workers/tasks_diagnostics.py` |
| 12 | BLUEPRINT update | ✅ | Documents findings, not the wrong hypothesis |

**Lessons for future plans:** Plan-time hypothesis testing on real data, even just a 30-line diagnostic script, would have caught both rejected hypotheses before any code was written. The TDD red-step in particular failed loudly here — the "failing test" passed organically because the threshold wasn't actually the bottleneck. Trust that signal.
