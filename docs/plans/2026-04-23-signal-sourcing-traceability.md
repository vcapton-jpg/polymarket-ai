# Signal Sourcing & Traceability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Axis A of the backend signal-quality effort — every signal persisted must carry (1) clickable source articles linked through a normalized `sources_registry` FK, (2) an LLM-generated 3–5-sentence `reasoning`, and (3) per-article `key_excerpt` verbatim-substring citations. Enforce these as hard invariants in the signal builder.

**Architecture:** Additive extension of the existing pipeline — no rewrite. Five migrations normalize/enrich the schema; the existing per-signal LLM call (`app/llm/impact_analyzer.py`) gains a structured-output variant with excerpts; the API's signal-detail endpoint is enriched with `sources[]`/`timeline[]`; three React components expose the data in `SignalDetail.tsx`. GDELT is added as a new ingestion source and RSSHub moves from the unreliable public host to a self-hosted container.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Celery (+beat), OpenAI (`gpt-4o-mini-2024-07-18`), pgvector/pg16, Docker Compose, React 18 + TypeScript + Vite, Vitest, Playwright.

**Source of truth:** [docs/specs/2026-04-23-signal-sourcing-traceability-design.md](../specs/2026-04-23-signal-sourcing-traceability-design.md)

---

## File Structure

**Migrations** (new files in `alembic/versions/`):
- `014_news_source_id_fk.py` — `news.source_id` FK + backfill
- `015_signal_reasoning.py` — `signals.reasoning`/`llm_model_version`/`source_tier_mix` + `signals_pending_reasoning` staging
- `016_event_news_link_excerpts.py` — `event_news_links.key_excerpt` + `relevance_score`
- `017_gdelt_events_raw.py` — GDELT staging table
- `018_rsshub_self_hosted_urls.py` — rewrite `rsshub.app` → `rsshub:1200`

**Backend** (modifications + new files):
- `app/db/models.py` — add fields to `News`, `Signal`, `EventNewsLink`; new `GdeltEventRaw`, `SignalPendingReasoning`
- `app/ingestion/gdelt_client.py` — **new**
- `app/workers/tasks_ingestion.py` — add `fetch_gdelt` task; `fetch_rss_feeds` writes `source_id`
- `app/llm/reasoning_analyzer.py` — **new** (structured output; excerpt substring validator; tier-mix computer)
- `app/llm/impact_analyzer.py` — left alone; `ReasoningAnalyzer` supersedes it in the signal flow
- `app/signal/signal_builder.py` — invariant enforcement (reject if no reasoning / no valid excerpts); persist `reasoning`, `source_tier_mix`, `key_excerpt`s
- `app/workers/tasks_scoring.py` — circuit-breaker on 429: push to `signals_pending_reasoning` instead of persisting
- `app/workers/tasks_scoring.py` — new `backfill_reasoning` task
- `app/api/routes/signals.py` (or wherever `GET /api/signals/{id}` lives) — enrich response; add `GET /api/signals/{id}/sources`
- `app/api/routes/sources.py` — **new** (`GET /api/sources` admin/debug)
- `app/api/schemas_v2.py` — add `SignalSourceOut`, `TimelineEventOut`, extend `SignalDetailOut`
- `scripts/backfill_reasoning.py` — **new** (one-off legacy backfill)
- `prompts/signal_reasoning_v1.txt` — **new** structured-output prompt
- `docker-compose.yml` — add `rsshub` service

**Frontend** (new + modifications):
- `frontend/src/types/signal.ts` — extend `Signal`; new `SignalSource`, `TimelineEvent`
- `frontend/src/components/signals/WhyThisMatters.tsx` — **new**
- `frontend/src/components/signals/SourcesList.tsx` — **new**
- `frontend/src/components/signals/SignalTimeline.tsx` — **new**
- `frontend/src/pages/SignalDetail.tsx` — integrate three new components
- `frontend/src/lib/api/signals.ts` — typed fetch of extended `Signal`

**Tests**:
- `tests/unit/test_migration_014.py` (new)
- `tests/unit/ingestion/test_gdelt_client.py` (new)
- `tests/unit/llm/test_reasoning_analyzer.py` (new)
- `tests/unit/signal/test_signal_builder_invariants.py` (new)
- `tests/integration/test_signal_detail_api.py` (new)
- `tests/integration/test_sources_api.py` (new)
- `frontend/src/components/signals/__tests__/WhyThisMatters.test.tsx` (new)
- `frontend/src/components/signals/__tests__/SourcesList.test.tsx` (new)
- `frontend/src/components/signals/__tests__/SignalTimeline.test.tsx` (new)
- `frontend/tests/e2e/signal-detail.spec.ts` (new Playwright)

---

## Task 1: Migration 014 — normalize `news` → `sources_registry`

**Files:**
- Create: `alembic/versions/014_news_source_id_fk.py`
- Test: `tests/unit/test_migration_014.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_migration_014.py
"""Migration 014 — news.source_id backfill coverage."""
import asyncio

import pytest
from sqlalchemy import text

from app.db.database import get_async_session_factory


@pytest.mark.asyncio
async def test_news_source_id_column_exists_after_upgrade():
    session_factory = get_async_session_factory()
    async with session_factory() as s:
        rows = (await s.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='news' AND column_name='source_id'"
        ))).all()
        assert rows, "news.source_id must exist after migration 014"


@pytest.mark.asyncio
async def test_news_source_id_index_exists():
    session_factory = get_async_session_factory()
    async with session_factory() as s:
        rows = (await s.execute(text(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename='news' AND indexname='ix_news_source_id'"
        ))).all()
        assert rows, "ix_news_source_id must exist"


@pytest.mark.asyncio
async def test_news_source_id_backfill_coverage():
    """Every news row whose source_name matches a registry row must have source_id set."""
    session_factory = get_async_session_factory()
    async with session_factory() as s:
        total = (await s.execute(text(
            "SELECT COUNT(*) FROM news n "
            "JOIN sources_registry sr ON n.source_name = sr.source_name"
        ))).scalar_one()
        matched = (await s.execute(text(
            "SELECT COUNT(*) FROM news n "
            "JOIN sources_registry sr ON n.source_name = sr.source_name "
            "WHERE n.source_id IS NOT NULL"
        ))).scalar_one()
        if total > 0:
            assert matched / total >= 0.95, f"Backfill coverage too low: {matched}/{total}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec app pytest tests/unit/test_migration_014.py -v
```

Expected: FAIL — column `news.source_id` does not exist.

- [ ] **Step 3: Write the migration**

```python
# alembic/versions/014_news_source_id_fk.py
"""normalize news.source_name to sources_registry via source_id FK

Revision ID: 014
Revises: 013
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "news",
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources_registry.id"), nullable=True),
    )
    op.create_index("ix_news_source_id", "news", ["source_id"])
    op.execute(
        """
        UPDATE news
        SET source_id = sr.id
        FROM sources_registry sr
        WHERE news.source_name = sr.source_name AND news.source_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_news_source_id", table_name="news")
    op.drop_column("news", "source_id")
```

- [ ] **Step 4: Apply and verify**

```bash
docker compose exec app alembic upgrade head
docker compose exec app pytest tests/unit/test_migration_014.py -v
```

Expected: PASS 3/3.

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/014_news_source_id_fk.py tests/unit/test_migration_014.py
git commit -m "feat(db): migration 014 — news.source_id FK + backfill"
```

---

## Task 2: Migration 015 — `signals.reasoning` + staging table

**Files:**
- Create: `alembic/versions/015_signal_reasoning.py`

- [ ] **Step 1: Write the migration**

```python
# alembic/versions/015_signal_reasoning.py
"""add reasoning + llm_model_version + source_tier_mix to signals; create signals_pending_reasoning

Revision ID: 015
Revises: 014
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signals", sa.Column("reasoning", sa.Text(), nullable=True))
    op.add_column("signals", sa.Column("llm_model_version", sa.String(length=50), nullable=True))
    op.add_column("signals", sa.Column("source_tier_mix", postgresql.JSONB(), nullable=True))

    op.create_table(
        "signals_pending_reasoning",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("market_id", sa.String(length=128), nullable=False),
        sa.Column("inputs", postgresql.JSONB(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_signals_pending_reasoning_created_at",
        "signals_pending_reasoning",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_signals_pending_reasoning_created_at", table_name="signals_pending_reasoning")
    op.drop_table("signals_pending_reasoning")
    op.drop_column("signals", "source_tier_mix")
    op.drop_column("signals", "llm_model_version")
    op.drop_column("signals", "reasoning")
```

- [ ] **Step 2: Apply and verify columns exist**

```bash
docker compose exec app alembic upgrade head
docker compose exec app python -c "
import asyncio
from sqlalchemy import text
from app.db.database import get_async_session_factory

async def main():
    async with get_async_session_factory()() as s:
        for col in ['reasoning', 'llm_model_version', 'source_tier_mix']:
            r = (await s.execute(text(
                \"SELECT 1 FROM information_schema.columns WHERE table_name='signals' AND column_name=:c\"
            ), {'c': col})).first()
            assert r, f'missing {col}'
        r = (await s.execute(text(
            \"SELECT 1 FROM information_schema.tables WHERE table_name='signals_pending_reasoning'\"
        ))).first()
        assert r
        print('OK')

asyncio.run(main())
"
```

Expected: prints `OK`.

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/015_signal_reasoning.py
git commit -m "feat(db): migration 015 — signals.reasoning + signals_pending_reasoning"
```

---

## Task 3: Migration 016 — article-level excerpts on `event_news_links`

**Files:**
- Create: `alembic/versions/016_event_news_link_excerpts.py`

- [ ] **Step 1: Write the migration**

```python
# alembic/versions/016_event_news_link_excerpts.py
"""add key_excerpt and relevance_score to event_news_links

Revision ID: 016
Revises: 015
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa


revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("event_news_links", sa.Column("key_excerpt", sa.Text(), nullable=True))
    op.add_column("event_news_links", sa.Column("relevance_score", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("event_news_links", "relevance_score")
    op.drop_column("event_news_links", "key_excerpt")
```

- [ ] **Step 2: Apply and verify**

```bash
docker compose exec app alembic upgrade head
docker compose exec app psql "$DATABASE_URL" -c "\d event_news_links" | grep -E "key_excerpt|relevance_score"
```

Expected: both columns listed.

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/016_event_news_link_excerpts.py
git commit -m "feat(db): migration 016 — event_news_links.key_excerpt + relevance_score"
```

---

## Task 4: Migration 017 — `gdelt_events_raw` staging

**Files:**
- Create: `alembic/versions/017_gdelt_events_raw.py`

- [ ] **Step 1: Write the migration**

```python
# alembic/versions/017_gdelt_events_raw.py
"""create gdelt_events_raw staging table

Revision ID: 017
Revises: 016
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gdelt_events_raw",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("gdelt_event_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor1", sa.Text(), nullable=True),
        sa.Column("actor2", sa.Text(), nullable=True),
        sa.Column("event_code", sa.String(length=10), nullable=True),
        sa.Column("tone", sa.Float(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_gdelt_events_raw_published_at",
        "gdelt_events_raw",
        ["published_at"],
        postgresql_ops={"published_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("ix_gdelt_events_raw_published_at", table_name="gdelt_events_raw")
    op.drop_table("gdelt_events_raw")
```

- [ ] **Step 2: Apply and verify**

```bash
docker compose exec app alembic upgrade head
docker compose exec app psql "$DATABASE_URL" -c "\d gdelt_events_raw"
```

Expected: table present with all columns.

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/017_gdelt_events_raw.py
git commit -m "feat(db): migration 017 — gdelt_events_raw staging"
```

---

## Task 5: Migration 018 — point X/Twitter sources to self-hosted RSSHub

**Files:**
- Create: `alembic/versions/018_rsshub_self_hosted_urls.py`

- [ ] **Step 1: Write the migration**

```python
# alembic/versions/018_rsshub_self_hosted_urls.py
"""rewrite rsshub.app → rsshub:1200 in sources_registry

Revision ID: 018
Revises: 017
Create Date: 2026-04-23
"""
from alembic import op


revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE sources_registry
        SET url = REPLACE(url, 'https://rsshub.app', 'http://rsshub:1200')
        WHERE source_type = 'x_rss' AND url LIKE 'https://rsshub.app%'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE sources_registry
        SET url = REPLACE(url, 'http://rsshub:1200', 'https://rsshub.app')
        WHERE source_type = 'x_rss' AND url LIKE 'http://rsshub:1200%'
        """
    )
```

- [ ] **Step 2: Apply and verify**

```bash
docker compose exec app alembic upgrade head
docker compose exec app psql "$DATABASE_URL" -c \
  "SELECT count(*) FROM sources_registry WHERE source_type='x_rss' AND url LIKE 'http://rsshub:1200%'"
```

Expected: count matches the seeded X/Twitter source count.

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/018_rsshub_self_hosted_urls.py
git commit -m "feat(db): migration 018 — rewrite rsshub.app URLs to self-hosted"
```

---

## Task 6: SQLAlchemy models — `News`, `Signal`, `EventNewsLink`, new `GdeltEventRaw`, `SignalPendingReasoning`

**Files:**
- Modify: `app/db/models.py`

- [ ] **Step 1: Read current models and add new columns**

Open `app/db/models.py`. Locate the `News` class and add after the `source_weight` column:

```python
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sources_registry.id"), nullable=True, index=True
    )
    source: Mapped[Optional["SourceRegistry"]] = relationship(
        "SourceRegistry", lazy="joined"
    )
```

Locate the `Signal` class and add after the `catalyst` column:

```python
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_tier_mix: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
```

Locate `EventNewsLink` and add:

```python
    key_excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
```

At the bottom of the file add:

```python
class GdeltEventRaw(Base):
    __tablename__ = "gdelt_events_raw"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    gdelt_event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actor1: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor2: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    tone: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SignalPendingReasoning(Base):
    __tablename__ = "signals_pending_reasoning"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    market_id: Mapped[str] = mapped_column(String(128), nullable=False)
    inputs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
```

Make sure the imports at the top include `BigInteger`, `Float`, `Text`, and `JSONB` (from `sqlalchemy` and `sqlalchemy.dialects.postgresql` respectively). If missing, add them.

- [ ] **Step 2: Verify models load without error**

```bash
docker compose exec app python -c "from app.db.models import News, Signal, EventNewsLink, GdeltEventRaw, SignalPendingReasoning; print('OK')"
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add app/db/models.py
git commit -m "feat(db): ORM models for source_id, reasoning, excerpts, gdelt, pending-reasoning"
```

---

## Task 7: GDELT client

**Files:**
- Create: `app/ingestion/gdelt_client.py`
- Test: `tests/unit/ingestion/test_gdelt_client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/ingestion/test_gdelt_client.py
"""GDELT client — payload parsing and dedupe."""
from unittest.mock import AsyncMock, patch

import pytest

from app.ingestion.gdelt_client import GdeltClient


SAMPLE_PAYLOAD = {
    "articles": [
        {
            "url": "https://www.reuters.com/world/article-1",
            "title": "Trump announces summit",
            "seendate": "20260423T140300Z",
            "domain": "reuters.com",
            "language": "English",
        },
        {
            "url": "https://www.reuters.com/world/article-1",  # duplicate
            "title": "Trump announces summit",
            "seendate": "20260423T140400Z",
            "domain": "reuters.com",
            "language": "English",
        },
        {
            "url": "https://bbc.co.uk/news/article-2",
            "title": "UN responds",
            "seendate": "20260423T145000Z",
            "domain": "bbc.co.uk",
            "language": "English",
        },
    ]
}


@pytest.mark.asyncio
async def test_fetch_recent_parses_and_dedupes():
    client = GdeltClient()
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=SAMPLE_PAYLOAD)
    mock_response.raise_for_status = lambda: None
    with patch.object(client, "_get", new=AsyncMock(return_value=SAMPLE_PAYLOAD)):
        arts = await client.fetch_recent("trump", timespan="15min")
    urls = [a["url"] for a in arts]
    assert len(arts) == 2
    assert "https://www.reuters.com/world/article-1" in urls
    assert "https://bbc.co.uk/news/article-2" in urls


@pytest.mark.asyncio
async def test_fetch_recent_extracts_source_name_from_domain():
    client = GdeltClient()
    with patch.object(client, "_get", new=AsyncMock(return_value=SAMPLE_PAYLOAD)):
        arts = await client.fetch_recent("trump")
    reuters = next(a for a in arts if "reuters" in a["url"])
    assert reuters["source_name"] == "reuters.com"


@pytest.mark.asyncio
async def test_fetch_recent_parses_seendate():
    client = GdeltClient()
    with patch.object(client, "_get", new=AsyncMock(return_value=SAMPLE_PAYLOAD)):
        arts = await client.fetch_recent("trump")
    a0 = arts[0]
    assert a0["publish_date"].isoformat().startswith("2026-04-23T14:03")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec app pytest tests/unit/ingestion/test_gdelt_client.py -v
```

Expected: FAIL — `app.ingestion.gdelt_client` does not exist.

- [ ] **Step 3: Implement the client**

```python
# app/ingestion/gdelt_client.py
"""GDELT 2.0 DOC API client — free, no key, 15-min timespan."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class GdeltClient:
    BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
    TIMEOUT_S = 20.0

    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.TIMEOUT_S) as c:
            r = await c.get(self.BASE_URL, params=params)
            r.raise_for_status()
            return r.json()

    async def fetch_recent(
        self,
        query: str,
        timespan: str = "15min",
        max_records: int = 250,
        lang: str = "sourcelang:eng",
    ) -> list[dict[str, Any]]:
        """Return deduped English articles for `query` within `timespan`."""
        params = {
            "query": f"{query} {lang}",
            "mode": "ArtList",
            "maxrecords": max_records,
            "format": "json",
            "timespan": timespan,
            "sort": "DateDesc",
        }
        try:
            data = await self._get(params)
        except httpx.HTTPError as e:
            logger.warning("GDELT fetch failed: %s", e)
            return []

        articles = data.get("articles") or []
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for a in articles:
            url = a.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            out.append(
                {
                    "url": url,
                    "title": a.get("title", "").strip(),
                    "text": "",
                    "source_name": (a.get("domain") or _domain_of(url)).lower(),
                    "publish_date": _parse_seendate(a.get("seendate")),
                    "language": a.get("language", "").lower(),
                }
            )
        return out


def _domain_of(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return (urlparse(url).hostname or "").lower().lstrip("www.")
    except Exception:
        return ""


def _parse_seendate(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
```

- [ ] **Step 4: Run tests**

```bash
docker compose exec app pytest tests/unit/ingestion/test_gdelt_client.py -v
```

Expected: PASS 3/3.

- [ ] **Step 5: Commit**

```bash
git add app/ingestion/gdelt_client.py tests/unit/ingestion/test_gdelt_client.py
git commit -m "feat(ingestion): GDELT 2.0 DOC API client"
```

---

## Task 8: `fetch_gdelt` Celery task + auto-create unknown sources

**Files:**
- Modify: `app/workers/tasks_ingestion.py`
- Modify: `app/workers/celery_app.py` (beat schedule)
- Test: `tests/unit/ingestion/test_fetch_gdelt_task.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/ingestion/test_fetch_gdelt_task.py
"""fetch_gdelt task — resolve/auto-create source, insert news with source_id."""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, text

from app.db.database import get_async_session_factory
from app.db.models import News, SourceRegistry
from app.workers.tasks_ingestion import _fetch_gdelt_async


CANNED = [
    {
        "url": "https://newdomain.example.com/a",
        "title": "Breaking news",
        "text": "",
        "source_name": "newdomain.example.com",
        "publish_date": None,
        "language": "english",
    }
]


@pytest.mark.asyncio
async def test_fetch_gdelt_autocreates_source_and_inserts_news():
    session_factory = get_async_session_factory()
    async with session_factory() as s:
        await s.execute(text(
            "DELETE FROM sources_registry WHERE source_name='newdomain.example.com'"
        ))
        await s.execute(text(
            "DELETE FROM news WHERE source_name='newdomain.example.com'"
        ))
        await s.commit()

    with patch(
        "app.workers.tasks_ingestion.GdeltClient.fetch_recent",
        new=AsyncMock(return_value=CANNED),
    ):
        inserted = await _fetch_gdelt_async(queries=["trump"])

    assert inserted >= 1
    async with session_factory() as s:
        src = (await s.execute(
            select(SourceRegistry).where(SourceRegistry.source_name == "newdomain.example.com")
        )).scalar_one()
        assert src.tier == 3
        assert abs((src.weight or 0) - 0.4) < 1e-6
        assert src.source_type == "gdelt_auto"

        n = (await s.execute(
            select(News).where(News.source_name == "newdomain.example.com")
        )).scalar_one()
        assert n.source_id == src.id
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec app pytest tests/unit/ingestion/test_fetch_gdelt_task.py -v
```

Expected: FAIL — `_fetch_gdelt_async` is not defined.

- [ ] **Step 3: Implement the task**

Append to `app/workers/tasks_ingestion.py`:

```python
from app.db.models import SourceRegistry, GdeltEventRaw  # add to existing imports
from app.ingestion.gdelt_client import GdeltClient


async def _resolve_or_create_source(session, source_name: str) -> int:
    from sqlalchemy import select
    row = (await session.execute(
        select(SourceRegistry).where(SourceRegistry.source_name == source_name)
    )).scalar_one_or_none()
    if row:
        return row.id
    row = SourceRegistry(
        source_name=source_name,
        tier=3,
        weight=0.4,
        active=True,
        source_type="gdelt_auto",
        url=f"https://{source_name}",
    )
    session.add(row)
    await session.flush()
    logger.info("sources_registry: auto-created source '%s' from GDELT", source_name)
    return row.id


async def _fetch_gdelt_async(queries: list[str] | None = None) -> int:
    """Run one GDELT ingestion pass across all active gdelt_query sources.

    Returns the number of inserted news rows.
    """
    from sqlalchemy import select
    from app.db.database import get_async_session_factory
    from app.db.models import News

    session_factory = get_async_session_factory()
    client = GdeltClient()
    inserted = 0

    async with session_factory() as s:
        if queries is None:
            rows = (await s.execute(
                select(SourceRegistry).where(
                    SourceRegistry.source_type == "gdelt_query",
                    SourceRegistry.active.is_(True),
                )
            )).scalars().all()
            queries = [r.source_name for r in rows] or ["trump", "fomc", "ceasefire", "crypto regulation"]

        for q in queries:
            try:
                arts = await client.fetch_recent(q, timespan="15min")
            except Exception as e:
                logger.exception("GDELT fetch failed for %r: %s", q, e)
                continue

            for a in arts:
                exists = (await s.execute(
                    select(News.id).where(News.url == a["url"])
                )).scalar_one_or_none()
                if exists:
                    continue
                source_id = await _resolve_or_create_source(s, a["source_name"])
                n = News(
                    url=a["url"],
                    title=a["title"],
                    content=a.get("text", ""),
                    source_name=a["source_name"],
                    source_id=source_id,
                    publish_date=a["publish_date"],
                )
                s.add(n)
                inserted += 1
        await s.commit()

    logger.info("fetch_gdelt: inserted=%d across queries=%d", inserted, len(queries))
    return inserted


@celery_app.task(name="tasks.fetch_gdelt")
def fetch_gdelt() -> int:
    import asyncio
    return asyncio.run(_fetch_gdelt_async())
```

Open `app/workers/celery_app.py` and add to the beat schedule:

```python
"fetch-gdelt-every-5min": {
    "task": "tasks.fetch_gdelt",
    "schedule": 300.0,
},
```

- [ ] **Step 4: Run the test**

```bash
docker compose exec app pytest tests/unit/ingestion/test_fetch_gdelt_task.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/workers/tasks_ingestion.py app/workers/celery_app.py tests/unit/ingestion/test_fetch_gdelt_task.py
git commit -m "feat(ingestion): fetch_gdelt Celery task + source auto-create"
```

---

## Task 9: `rss_scraper` writes `source_id`

**Files:**
- Modify: `app/ingestion/rss_scraper.py`
- Test: `tests/unit/ingestion/test_rss_scraper_source_id.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/ingestion/test_rss_scraper_source_id.py
"""rss_scraper inserts News rows with source_id populated."""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.db.database import get_async_session_factory
from app.db.models import News, SourceRegistry
from app.ingestion.rss_scraper import RssScraper


@pytest.mark.asyncio
async def test_insert_sets_source_id_from_registry():
    session_factory = get_async_session_factory()
    async with session_factory() as s:
        src = (await s.execute(
            select(SourceRegistry).where(SourceRegistry.source_type == "rss").limit(1)
        )).scalar_one()

    item = {
        "url": "https://example.com/unit-test-article",
        "title": "Test",
        "content": "body",
        "publish_date": None,
    }
    scraper = RssScraper()
    await scraper._insert_news(item, source=src)

    async with session_factory() as s:
        n = (await s.execute(
            select(News).where(News.url == item["url"])
        )).scalar_one()
        assert n.source_id == src.id
        await s.delete(n)
        await s.commit()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec app pytest tests/unit/ingestion/test_rss_scraper_source_id.py -v
```

Expected: FAIL — `_insert_news` may not exist with that signature or source_id is not set.

- [ ] **Step 3: Update `_insert_news`**

In `app/ingestion/rss_scraper.py`, find the News-insertion path and ensure it sets `source_id=source.id` whenever a `SourceRegistry` row is available. Example shape:

```python
async def _insert_news(self, item: dict, source: SourceRegistry) -> None:
    from app.db.database import get_async_session_factory
    session_factory = get_async_session_factory()
    async with session_factory() as s:
        n = News(
            url=item["url"],
            title=item["title"],
            content=item.get("content", ""),
            source_name=source.source_name,
            source_id=source.id,
            source_tier=source.tier,
            source_weight=source.weight,
            publish_date=item.get("publish_date"),
        )
        s.add(n)
        await s.commit()
```

Replace or update the existing insertion call site to use the new shape. Keep backwards-compatible behavior for any code path that doesn't pass a `source`.

- [ ] **Step 4: Run the test**

```bash
docker compose exec app pytest tests/unit/ingestion/test_rss_scraper_source_id.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/ingestion/rss_scraper.py tests/unit/ingestion/test_rss_scraper_source_id.py
git commit -m "feat(ingestion): RSS scraper writes source_id to news"
```

---

## Task 10: Self-hosted RSSHub service

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add the service**

Add to `docker-compose.yml` under `services:`:

```yaml
  rsshub:
    image: diygod/rsshub:latest
    restart: unless-stopped
    environment:
      CACHE_TYPE: redis
      REDIS_URL: redis://redis:6379/5
      NODE_ENV: production
    depends_on:
      redis:
        condition: service_healthy
    ports:
      - "1200:1200"
    networks:
      - default
```

(If the compose file uses a named network for `app`/`redis`, reuse that same network name in place of `default`.)

- [ ] **Step 2: Start and smoke-test**

```bash
docker compose up -d rsshub
sleep 5
curl -sf http://localhost:1200/healthz && echo "OK"
```

Expected: `OK` (or 200 on `/`).

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(infra): self-hosted RSSHub container"
```

---

## Task 11: LLM reasoning analyzer with structured output + excerpt validation

**Files:**
- Create: `app/llm/reasoning_analyzer.py`
- Create: `prompts/signal_reasoning_v1.txt`
- Test: `tests/unit/llm/test_reasoning_analyzer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/llm/test_reasoning_analyzer.py
"""ReasoningAnalyzer — structured output, excerpt validation, tier-mix."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.llm.reasoning_analyzer import (
    ReasoningAnalyzer,
    compute_tier_mix,
    validate_output,
)


ARTICLES = [
    {
        "news_clean_id": 1,
        "title": "Reuters: Summit confirmed",
        "source_name": "Reuters Top News",
        "source_tier": 1,
        "clean_text": "Reuters reported today that the summit is confirmed for April 28.",
        "publish_date": "2026-04-23T14:03:00Z",
    },
    {
        "news_clean_id": 2,
        "title": "BBC: Officials agree",
        "source_name": "BBC News",
        "source_tier": 1,
        "clean_text": "BBC sources confirmed officials agreed on the date.",
        "publish_date": "2026-04-23T14:47:00Z",
    },
]


def test_compute_tier_mix_counts():
    mix = compute_tier_mix(ARTICLES)
    assert mix == {"tier_1": 2}


def test_validate_output_accepts_valid():
    out = {
        "impact_score": 0.7,
        "confidence": 0.8,
        "catalyst": "Summit confirmed",
        "reasoning": (
            "Reuters reported the summit is confirmed for April 28, and BBC corroborates. "
            "This directly addresses the market resolution criteria. Convergence between "
            "Reuters Top News and BBC News raises conviction."
        ),
        "direction_recommendation": "YES",
        "article_excerpts": [
            {"news_clean_id": 1, "excerpt": "the summit is confirmed for April 28", "relevance": 0.9},
            {"news_clean_id": 2, "excerpt": "officials agreed on the date", "relevance": 0.8},
        ],
    }
    errs, cleaned = validate_output(out, ARTICLES)
    assert errs == []
    assert len(cleaned["article_excerpts"]) == 2


def test_validate_output_rejects_short_reasoning():
    out = {
        "impact_score": 0.7, "confidence": 0.8, "catalyst": "x",
        "reasoning": "Too short.",
        "direction_recommendation": "YES",
        "article_excerpts": [
            {"news_clean_id": 1, "excerpt": "the summit is confirmed for April 28", "relevance": 0.9}
        ],
    }
    errs, _ = validate_output(out, ARTICLES)
    assert any("reasoning" in e.lower() for e in errs)


def test_validate_output_rejects_reasoning_without_source_name():
    out = {
        "impact_score": 0.7, "confidence": 0.8, "catalyst": "x",
        "reasoning": "x" * 120 + " Something that is long enough but never cites a registered source name.",
        "direction_recommendation": "YES",
        "article_excerpts": [
            {"news_clean_id": 1, "excerpt": "the summit is confirmed for April 28", "relevance": 0.9}
        ],
    }
    errs, _ = validate_output(out, ARTICLES)
    assert any("source name" in e.lower() for e in errs)


def test_validate_output_drops_non_substring_excerpts():
    out = {
        "impact_score": 0.7, "confidence": 0.8, "catalyst": "x",
        "reasoning": (
            "Reuters Top News and BBC News both confirm the summit date, which addresses "
            "the market resolution criteria. Convergence raises conviction that the outcome lands YES."
        ),
        "direction_recommendation": "YES",
        "article_excerpts": [
            {"news_clean_id": 1, "excerpt": "the summit is confirmed for April 28", "relevance": 0.9},
            {"news_clean_id": 2, "excerpt": "PARAPHRASED CONTENT NOT IN SOURCE", "relevance": 0.7},
        ],
    }
    errs, cleaned = validate_output(out, ARTICLES)
    assert errs == []
    assert len(cleaned["article_excerpts"]) == 1
    assert cleaned["article_excerpts"][0]["news_clean_id"] == 1


def test_validate_output_rejects_when_zero_valid_excerpts():
    out = {
        "impact_score": 0.7, "confidence": 0.8, "catalyst": "x",
        "reasoning": (
            "Reuters Top News and BBC News cover the story but none of the quoted "
            "phrases survive verification. The signal cannot be trusted without excerpts."
        ),
        "direction_recommendation": "YES",
        "article_excerpts": [
            {"news_clean_id": 1, "excerpt": "paraphrased", "relevance": 0.9},
            {"news_clean_id": 2, "excerpt": "also paraphrased", "relevance": 0.8},
        ],
    }
    errs, _ = validate_output(out, ARTICLES)
    assert any("excerpt" in e.lower() for e in errs)


@pytest.mark.asyncio
async def test_analyze_parses_and_validates():
    analyzer = ReasoningAnalyzer()
    mock_resp = {
        "impact_score": 0.7,
        "confidence": 0.8,
        "catalyst": "Summit confirmed",
        "reasoning": (
            "Reuters Top News reported the summit date, and BBC News corroborates the "
            "convergence. This addresses the market resolution criteria. Conviction is high."
        ),
        "direction_recommendation": "YES",
        "article_excerpts": [
            {"news_clean_id": 1, "excerpt": "the summit is confirmed for April 28", "relevance": 0.9}
        ],
    }
    with patch.object(
        analyzer.client, "chat_completion",
        new=AsyncMock(return_value=json.dumps(mock_resp)),
    ):
        result = await analyzer.analyze(
            event_title="Summit",
            event_summary="Summit is happening",
            articles=ARTICLES,
            market_question="Will summit happen by May 1?",
            market_price=0.55,
        )
    assert result is not None
    assert result["reasoning"].startswith("Reuters")
    assert len(result["article_excerpts"]) == 1
    assert result["source_tier_mix"] == {"tier_1": 2}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec app pytest tests/unit/llm/test_reasoning_analyzer.py -v
```

Expected: FAIL — module does not exist.

- [ ] **Step 3: Write the prompt**

Create `prompts/signal_reasoning_v1.txt`:

```
You are a prediction-market analyst. Given an event, a candidate Polymarket market, and up to 5 source articles, output a JSON object assessing whether and why these news items move THIS specific market.

Rules (all mandatory):
1. `reasoning` MUST be 200–400 characters, 3–5 sentences, and MUST cite at least one article by its `source_name` as given in the input.
2. Each `article_excerpts[].excerpt` MUST be a LITERAL substring of the corresponding article's `clean_text`. Paraphrases are forbidden.
3. If no article is genuinely relevant to this market, set `direction_recommendation="UNCLEAR"` and explain briefly in `reasoning`.
4. `catalyst` ≤ 120 characters; a short headline fit for notification display.
5. `impact_score` and `confidence` are floats in [0.0, 1.0].

Output JSON schema:
{
  "impact_score": float,
  "confidence": float,
  "catalyst": string,
  "reasoning": string,
  "direction_recommendation": "YES" | "NO" | "UNCLEAR",
  "article_excerpts": [
    {"news_clean_id": int, "excerpt": string, "relevance": float}
  ]
}
```

- [ ] **Step 4: Implement the analyzer**

```python
# app/llm/reasoning_analyzer.py
"""Per-signal LLM reasoning analyzer — structured output with excerpt validation."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.llm.openai_client import get_openai_client

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "signal_reasoning_v1.txt"

MIN_REASONING_CHARS = 100
MAX_REASONING_CHARS = 600


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def compute_tier_mix(articles: list[dict[str, Any]]) -> dict[str, int]:
    mix: dict[str, int] = {}
    for a in articles:
        tier = a.get("source_tier")
        if tier is None:
            continue
        mix[f"tier_{int(tier)}"] = mix.get(f"tier_{int(tier)}", 0) + 1
    return mix


def validate_output(
    out: dict[str, Any], articles: list[dict[str, Any]]
) -> tuple[list[str], dict[str, Any]]:
    """Return (errors, cleaned_output). If errors is non-empty the signal must be rejected."""
    errs: list[str] = []
    reasoning = (out.get("reasoning") or "").strip()
    if len(reasoning) < MIN_REASONING_CHARS:
        errs.append(f"reasoning too short ({len(reasoning)} chars, need >= {MIN_REASONING_CHARS})")

    source_names = {a["source_name"] for a in articles}
    if not any(sn in reasoning for sn in source_names):
        errs.append("reasoning does not cite any input source name")

    text_by_id = {a["news_clean_id"]: a["clean_text"] for a in articles}
    cleaned_excerpts: list[dict[str, Any]] = []
    for e in out.get("article_excerpts") or []:
        nid = e.get("news_clean_id")
        exc = (e.get("excerpt") or "").strip()
        if nid in text_by_id and exc and exc in text_by_id[nid]:
            cleaned_excerpts.append(
                {"news_clean_id": nid, "excerpt": exc, "relevance": float(e.get("relevance", 0.0))}
            )

    if not cleaned_excerpts:
        errs.append("zero valid excerpt substrings")

    cleaned = dict(out)
    cleaned["article_excerpts"] = cleaned_excerpts
    cleaned["source_tier_mix"] = compute_tier_mix(articles)
    return errs, cleaned


class ReasoningAnalyzer:
    def __init__(self) -> None:
        self.client = get_openai_client()
        self.system_prompt = _load_prompt()
        self._model = getattr(
            get_settings(), "openai_reasoning_model", "gpt-4o-mini-2024-07-18"
        )

    @property
    def model_version(self) -> str:
        return self._model

    async def analyze(
        self,
        *,
        event_title: str,
        event_summary: str,
        articles: list[dict[str, Any]],
        market_question: str,
        market_price: float,
        market_direction_hint: str | None = None,
    ) -> dict[str, Any] | None:
        articles_for_prompt = [
            {
                "news_clean_id": a["news_clean_id"],
                "title": a["title"],
                "source_name": a["source_name"],
                "publish_date": a.get("publish_date"),
                "clean_text": a["clean_text"][:800],
            }
            for a in articles[:5]
        ]
        user_msg = json.dumps(
            {
                "event": {"title": event_title, "summary": event_summary},
                "market": {
                    "question": market_question,
                    "price": market_price,
                    "direction_hint": market_direction_hint,
                },
                "articles": articles_for_prompt,
            },
            ensure_ascii=False,
        )

        try:
            raw = await self.client.chat_completion(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                call_type="signal_reasoning",
                model=self._model,
                max_tokens=700,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            logger.warning("ReasoningAnalyzer: LLM call failed: %s", e)
            raise

        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("ReasoningAnalyzer: invalid JSON from LLM")
            return None

        errs, cleaned = validate_output(parsed, articles)
        if errs:
            logger.info("ReasoningAnalyzer rejected: %s", errs)
            return None
        return cleaned


def create_reasoning_analyzer() -> ReasoningAnalyzer:
    return ReasoningAnalyzer()
```

- [ ] **Step 5: Run tests**

```bash
docker compose exec app pytest tests/unit/llm/test_reasoning_analyzer.py -v
```

Expected: PASS 7/7.

- [ ] **Step 6: Commit**

```bash
git add app/llm/reasoning_analyzer.py prompts/signal_reasoning_v1.txt tests/unit/llm/test_reasoning_analyzer.py
git commit -m "feat(llm): reasoning analyzer with structured output + excerpt validation"
```

---

## Task 12: Signal builder invariant enforcement

**Files:**
- Modify: `app/signal/signal_builder.py`
- Test: `tests/unit/signal/test_signal_builder_invariants.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/signal/test_signal_builder_invariants.py
"""Signal builder — reject if no reasoning or no valid excerpts; persist sources."""
from unittest.mock import AsyncMock

import pytest

from app.signal.signal_builder import build_signal


@pytest.mark.asyncio
async def test_rejects_when_reasoning_is_none():
    analyzer = AsyncMock()
    analyzer.analyze = AsyncMock(return_value=None)
    analyzer.model_version = "gpt-4o-mini-2024-07-18"
    result = await build_signal(
        event={"id": 1, "title": "t", "summary": "s"},
        market={"id": "m1", "question": "q?", "price": 0.5},
        articles=[{
            "news_clean_id": 1, "title": "x", "source_name": "Reuters Top News",
            "source_tier": 1, "clean_text": "body", "publish_date": None,
        }],
        analyzer=analyzer,
        persist=False,
    )
    assert result is None


@pytest.mark.asyncio
async def test_persists_when_valid():
    analyzer = AsyncMock()
    analyzer.model_version = "gpt-4o-mini-2024-07-18"
    analyzer.analyze = AsyncMock(return_value={
        "impact_score": 0.8, "confidence": 0.9,
        "catalyst": "Summit confirmed",
        "reasoning": (
            "Reuters Top News confirms the summit, and this directly addresses the market "
            "resolution criteria. Convergence of reporting raises conviction. The direction is YES."
        ),
        "direction_recommendation": "YES",
        "article_excerpts": [
            {"news_clean_id": 1, "excerpt": "summit confirmed", "relevance": 0.9}
        ],
        "source_tier_mix": {"tier_1": 1},
    })
    result = await build_signal(
        event={"id": 1, "title": "t", "summary": "s"},
        market={"id": "m1", "question": "q?", "price": 0.5},
        articles=[{
            "news_clean_id": 1, "title": "x", "source_name": "Reuters Top News",
            "source_tier": 1, "clean_text": "summit confirmed today", "publish_date": None,
        }],
        analyzer=analyzer,
        persist=False,
    )
    assert result is not None
    assert result["reasoning"].startswith("Reuters")
    assert result["source_tier_mix"] == {"tier_1": 1}
    assert result["llm_model_version"] == "gpt-4o-mini-2024-07-18"
    assert len(result["article_excerpts"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec app pytest tests/unit/signal/test_signal_builder_invariants.py -v
```

Expected: FAIL — `build_signal` signature not yet exposed / does not enforce invariant.

- [ ] **Step 3: Add `build_signal` entry point to `app/signal/signal_builder.py`**

Append to `app/signal/signal_builder.py`:

```python
async def build_signal(
    *,
    event: dict,
    market: dict,
    articles: list[dict],
    analyzer,
    persist: bool = True,
) -> dict | None:
    """Build a signal enforcing the post-Axis-A invariant.

    Returns the assembled signal dict on success, None if the signal is rejected
    (missing reasoning or missing valid excerpts).
    When persist=True and the caller passes a session, it commits to DB.
    """
    try:
        llm = await analyzer.analyze(
            event_title=event["title"],
            event_summary=event.get("summary", ""),
            articles=articles,
            market_question=market["question"],
            market_price=float(market.get("price", 0.0)),
            market_direction_hint=market.get("direction_hint"),
        )
    except Exception as e:
        logger.info("build_signal: analyzer failed, rejecting: %s", e)
        return None

    if llm is None:
        logger.info(
            "signals.rejected_no_reasoning event_id=%s market_id=%s",
            event.get("id"), market.get("id"),
        )
        return None

    if not llm.get("article_excerpts"):
        logger.info(
            "signals.rejected_no_excerpts event_id=%s market_id=%s",
            event.get("id"), market.get("id"),
        )
        return None

    assembled = {
        "event_id": event["id"],
        "market_id": market["id"],
        "catalyst": llm.get("catalyst"),
        "reasoning": llm["reasoning"],
        "llm_model_version": getattr(analyzer, "model_version", None),
        "source_tier_mix": llm.get("source_tier_mix"),
        "impact_score": llm.get("impact_score"),
        "confidence": llm.get("confidence"),
        "direction_recommendation": llm.get("direction_recommendation"),
        "article_excerpts": llm["article_excerpts"],
    }

    if persist:
        await _persist_signal(assembled, articles)
    return assembled


async def _persist_signal(assembled: dict, articles: list[dict]) -> None:
    from sqlalchemy import update
    from app.db.database import get_async_session_factory
    from app.db.models import EventNewsLink, Signal

    session_factory = get_async_session_factory()
    async with session_factory() as s:
        sig = Signal(
            event_id=assembled["event_id"],
            market_id=assembled["market_id"],
            catalyst=assembled["catalyst"],
            reasoning=assembled["reasoning"],
            llm_model_version=assembled["llm_model_version"],
            source_tier_mix=assembled["source_tier_mix"],
        )
        s.add(sig)
        for exc in assembled["article_excerpts"]:
            await s.execute(
                update(EventNewsLink)
                .where(
                    EventNewsLink.event_id == assembled["event_id"],
                    EventNewsLink.clean_id == exc["news_clean_id"],
                )
                .values(key_excerpt=exc["excerpt"], relevance_score=exc["relevance"])
            )
        await s.commit()
```

- [ ] **Step 4: Run the tests**

```bash
docker compose exec app pytest tests/unit/signal/test_signal_builder_invariants.py -v
```

Expected: PASS 2/2.

- [ ] **Step 5: Commit**

```bash
git add app/signal/signal_builder.py tests/unit/signal/test_signal_builder_invariants.py
git commit -m "feat(signals): build_signal invariant — reasoning + valid excerpts required"
```

---

## Task 13: Wire `build_signal` into the scoring worker + circuit-breaker on 429

**Files:**
- Modify: `app/workers/tasks_scoring.py`
- Test: `tests/unit/scoring/test_scoring_quota_circuit_breaker.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/scoring/test_scoring_quota_circuit_breaker.py
"""On 429, the signal is pushed to signals_pending_reasoning instead of persisted."""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.db.database import get_async_session_factory
from app.db.models import Signal, SignalPendingReasoning
from app.workers.tasks_scoring import _score_event_market_async


@pytest.mark.asyncio
async def test_quota_exceeded_writes_pending_row():
    class Quota429(Exception):
        pass

    analyzer = AsyncMock()
    analyzer.model_version = "gpt-4o-mini-2024-07-18"
    analyzer.analyze = AsyncMock(side_effect=Quota429("insufficient_quota"))

    event = {"id": 1, "title": "t", "summary": "s"}
    market = {"id": "m-quota-test", "question": "q?", "price": 0.5}
    articles = [{
        "news_clean_id": 1, "title": "x", "source_name": "Reuters Top News",
        "source_tier": 1, "clean_text": "body", "publish_date": None,
    }]

    with patch("app.workers.tasks_scoring._is_quota_error", return_value=True):
        out = await _score_event_market_async(event, market, articles, analyzer=analyzer)
    assert out is None

    session_factory = get_async_session_factory()
    async with session_factory() as s:
        row = (await s.execute(
            select(SignalPendingReasoning).where(SignalPendingReasoning.market_id == "m-quota-test")
        )).scalar_one_or_none()
        assert row is not None
        assert row.event_id == 1
        no_sig = (await s.execute(
            select(Signal).where(Signal.market_id == "m-quota-test")
        )).scalar_one_or_none()
        assert no_sig is None
        await s.delete(row)
        await s.commit()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec app pytest tests/unit/scoring/test_scoring_quota_circuit_breaker.py -v
```

Expected: FAIL.

- [ ] **Step 3: Add circuit-breaker logic**

Append to `app/workers/tasks_scoring.py`:

```python
def _is_quota_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return (
        "insufficient_quota" in msg
        or "quota" in msg
        or "429" in msg
        or "rate limit" in msg
    )


async def _score_event_market_async(event, market, articles, *, analyzer=None):
    from app.llm.reasoning_analyzer import create_reasoning_analyzer
    from app.signal.signal_builder import build_signal
    from app.db.database import get_async_session_factory
    from app.db.models import SignalPendingReasoning

    analyzer = analyzer or create_reasoning_analyzer()

    try:
        return await build_signal(
            event=event, market=market, articles=articles,
            analyzer=analyzer, persist=True,
        )
    except Exception as e:
        if _is_quota_error(e):
            logger.warning(
                "llm.quota_exceeded event_id=%s market_id=%s — staging for backfill",
                event.get("id"), market.get("id"),
            )
            session_factory = get_async_session_factory()
            async with session_factory() as s:
                s.add(SignalPendingReasoning(
                    event_id=event["id"],
                    market_id=market["id"],
                    inputs={
                        "event": event, "market": market, "articles": articles,
                    },
                    last_error=str(e)[:500],
                ))
                await s.commit()
            return None
        raise
```

Wire this into the existing scoring task dispatcher (find the place where signals are currently created from an event+market+articles triple and replace it with a call to `_score_event_market_async`). Keep older code paths intact behind a feature flag if needed; otherwise replace.

- [ ] **Step 4: Run the test**

```bash
docker compose exec app pytest tests/unit/scoring/test_scoring_quota_circuit_breaker.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/workers/tasks_scoring.py tests/unit/scoring/test_scoring_quota_circuit_breaker.py
git commit -m "feat(scoring): circuit-breaker on LLM quota — stage to signals_pending_reasoning"
```

---

## Task 14: `backfill_reasoning` Celery task

**Files:**
- Modify: `app/workers/tasks_scoring.py` (new task)
- Modify: `app/workers/celery_app.py` (beat schedule)
- Test: `tests/unit/scoring/test_backfill_reasoning.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/scoring/test_backfill_reasoning.py
"""backfill_reasoning drains signals_pending_reasoning once LLM works again."""
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.db.database import get_async_session_factory
from app.db.models import Signal, SignalPendingReasoning
from app.workers.tasks_scoring import _backfill_reasoning_async


@pytest.mark.asyncio
async def test_backfill_drains_pending_on_success():
    session_factory = get_async_session_factory()
    async with session_factory() as s:
        pending = SignalPendingReasoning(
            event_id=1,
            market_id="m-backfill-test",
            inputs={
                "event": {"id": 1, "title": "t", "summary": "s"},
                "market": {"id": "m-backfill-test", "question": "q?", "price": 0.5},
                "articles": [{
                    "news_clean_id": 1, "title": "x", "source_name": "Reuters Top News",
                    "source_tier": 1, "clean_text": "summit confirmed today", "publish_date": None,
                }],
            },
        )
        s.add(pending)
        await s.commit()

    analyzer = AsyncMock()
    analyzer.model_version = "gpt-4o-mini-2024-07-18"
    analyzer.analyze = AsyncMock(return_value={
        "impact_score": 0.8, "confidence": 0.9, "catalyst": "Summit confirmed",
        "reasoning": (
            "Reuters Top News confirms the summit, addressing the market resolution criteria "
            "directly. Convergence raises conviction and direction is YES."
        ),
        "direction_recommendation": "YES",
        "article_excerpts": [
            {"news_clean_id": 1, "excerpt": "summit confirmed today", "relevance": 0.9}
        ],
        "source_tier_mix": {"tier_1": 1},
    })

    n = await _backfill_reasoning_async(limit=10, analyzer=analyzer)
    assert n >= 1
    async with session_factory() as s:
        leftover = (await s.execute(
            select(SignalPendingReasoning).where(SignalPendingReasoning.market_id == "m-backfill-test")
        )).scalar_one_or_none()
        assert leftover is None
        sig = (await s.execute(
            select(Signal).where(Signal.market_id == "m-backfill-test")
        )).scalar_one()
        assert sig.reasoning.startswith("Reuters")
        await s.delete(sig)
        await s.commit()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec app pytest tests/unit/scoring/test_backfill_reasoning.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement the task**

Append to `app/workers/tasks_scoring.py`:

```python
async def _backfill_reasoning_async(limit: int = 50, *, analyzer=None) -> int:
    from sqlalchemy import delete, select
    from app.db.database import get_async_session_factory
    from app.db.models import SignalPendingReasoning
    from app.signal.signal_builder import build_signal
    from app.llm.reasoning_analyzer import create_reasoning_analyzer

    analyzer = analyzer or create_reasoning_analyzer()

    session_factory = get_async_session_factory()
    done = 0
    async with session_factory() as s:
        rows = (await s.execute(
            select(SignalPendingReasoning).order_by(SignalPendingReasoning.created_at).limit(limit)
        )).scalars().all()

    for row in rows:
        inputs = row.inputs or {}
        try:
            result = await build_signal(
                event=inputs["event"],
                market=inputs["market"],
                articles=inputs["articles"],
                analyzer=analyzer,
                persist=True,
            )
        except Exception as e:
            if _is_quota_error(e):
                logger.warning("backfill_reasoning: quota still exceeded, stopping")
                break
            async with session_factory() as s:
                s.add(row)  # re-attach
                row.attempts = (row.attempts or 0) + 1
                row.last_error = str(e)[:500]
                await s.commit()
            continue

        async with session_factory() as s:
            await s.execute(
                delete(SignalPendingReasoning).where(SignalPendingReasoning.id == row.id)
            )
            await s.commit()
        if result is not None:
            done += 1
    logger.info("backfill_reasoning: drained=%d", done)
    return done


@celery_app.task(name="tasks.backfill_reasoning")
def backfill_reasoning() -> int:
    import asyncio
    return asyncio.run(_backfill_reasoning_async())
```

Add to `app/workers/celery_app.py` beat schedule:

```python
"backfill-reasoning-every-10min": {
    "task": "tasks.backfill_reasoning",
    "schedule": 600.0,
},
```

- [ ] **Step 4: Run the test**

```bash
docker compose exec app pytest tests/unit/scoring/test_backfill_reasoning.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/workers/tasks_scoring.py app/workers/celery_app.py tests/unit/scoring/test_backfill_reasoning.py
git commit -m "feat(scoring): backfill_reasoning task drains signals_pending_reasoning"
```

---

## Task 15: Enrich `GET /api/signals/{id}` with sources, reasoning, timeline

**Files:**
- Modify: `app/api/schemas_v2.py`
- Modify: `app/api/routes/` (whichever route serves signal detail — likely `app/api/signal_mapper.py` + a signals route)
- Test: `tests/integration/test_signal_detail_api.py`

- [ ] **Step 1: Add response schemas**

In `app/api/schemas_v2.py` add:

```python
from typing import Literal, Optional

from pydantic import BaseModel


class SignalSourceOut(BaseModel):
    news_id: int
    title: str
    url: str
    source_name: str
    source_tier: int
    source_weight: float | None = None
    publish_date: str | None = None
    excerpt: str | None = None
    relevance_score: float | None = None
    role: Literal["primary", "supporting"] = "supporting"


class TimelineEventOut(BaseModel):
    at: str
    source: str
    type: Literal["news", "market_move"] = "news"
    headline: str | None = None
    detail: str | None = None
```

Then extend the existing `SignalDetailOut` (or add it if missing) with:

```python
    reasoning: str | None = None
    llm_model_version: str | None = None
    source_tier_mix: dict[str, int] | None = None
    sources: list[SignalSourceOut] = []
    timeline: list[TimelineEventOut] = []
```

- [ ] **Step 2: Write the failing integration test**

```python
# tests/integration/test_signal_detail_api.py
"""Signal detail endpoint — sources sorted, tier_mix consistent, null-reasoning legacy safe."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_detail_returns_sources_sorted_by_relevance(seeded_signal_with_three_sources):
    signal_id = seeded_signal_with_three_sources["id"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r = await client.get(f"/api/signals/{signal_id}")
    assert r.status_code == 200
    data = r.json()
    scores = [s["relevance_score"] for s in data["sources"]]
    assert scores == sorted(scores, reverse=True)
    tier_counts = {"tier_1": 0, "tier_2": 0, "tier_3": 0}
    for s in data["sources"]:
        tier_counts[f"tier_{s['source_tier']}"] += 1
    for k, v in (data["source_tier_mix"] or {}).items():
        assert tier_counts.get(k, 0) == v


@pytest.mark.asyncio
async def test_detail_on_legacy_signal_returns_null_reasoning(seeded_legacy_signal):
    signal_id = seeded_legacy_signal["id"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r = await client.get(f"/api/signals/{signal_id}")
    assert r.status_code == 200
    assert r.json()["reasoning"] is None
```

Add the corresponding fixtures in `tests/integration/conftest.py` (create if absent):

```python
import pytest
from sqlalchemy import text

from app.db.database import get_async_session_factory


@pytest.fixture
async def seeded_signal_with_three_sources():
    session_factory = get_async_session_factory()
    async with session_factory() as s:
        event_id = (await s.execute(text(
            "INSERT INTO events (title, summary, created_at) "
            "VALUES ('E','S', NOW()) RETURNING id"
        ))).scalar_one()

        news_ids: list[int] = []
        for i, (name, tier, rel) in enumerate([
            ("Reuters Top News", 1, 0.9),
            ("BBC News", 1, 0.7),
            ("Some Blog", 3, 0.4),
        ]):
            news_id = (await s.execute(text(
                "INSERT INTO news (url, title, content, source_name, source_tier, source_weight, publish_date) "
                "VALUES (:u, :t, :c, :n, :tier, :w, NOW()) RETURNING id"
            ), {
                "u": f"https://example.com/{i}", "t": f"t{i}", "c": "body",
                "n": name, "tier": tier, "w": 1.0,
            })).scalar_one()
            clean_id = (await s.execute(text(
                "INSERT INTO news_clean (news_id, clean_text) VALUES (:n, 'body text') RETURNING id"
            ), {"n": news_id})).scalar_one()
            await s.execute(text(
                "INSERT INTO event_news_links (event_id, clean_id, key_excerpt, relevance_score) "
                "VALUES (:e, :c, :exc, :rel)"
            ), {"e": event_id, "c": clean_id, "exc": "body text", "rel": rel})
            news_ids.append(news_id)

        sig_id = (await s.execute(text(
            "INSERT INTO signals (event_id, market_id, catalyst, reasoning, llm_model_version, source_tier_mix, created_at) "
            "VALUES (:e, 'mtest', 'cat', 'Reuters Top News and BBC News confirm — reasoning long enough.', 'gpt-4o-mini-2024-07-18', "
            "'{\"tier_1\": 2, \"tier_3\": 1}'::jsonb, NOW()) RETURNING id"
        ), {"e": event_id})).scalar_one()
        await s.commit()
        yield {"id": sig_id, "event_id": event_id, "news_ids": news_ids}

        await s.execute(text("DELETE FROM signals WHERE id=:id"), {"id": sig_id})
        await s.execute(text("DELETE FROM event_news_links WHERE event_id=:e"), {"e": event_id})
        await s.execute(text("DELETE FROM news_clean WHERE news_id = ANY(:ids)"), {"ids": news_ids})
        await s.execute(text("DELETE FROM news WHERE id = ANY(:ids)"), {"ids": news_ids})
        await s.execute(text("DELETE FROM events WHERE id=:e"), {"e": event_id})
        await s.commit()


@pytest.fixture
async def seeded_legacy_signal():
    session_factory = get_async_session_factory()
    async with session_factory() as s:
        event_id = (await s.execute(text(
            "INSERT INTO events (title, summary, created_at) VALUES ('legacy','s', NOW()) RETURNING id"
        ))).scalar_one()
        sig_id = (await s.execute(text(
            "INSERT INTO signals (event_id, market_id, catalyst, created_at) "
            "VALUES (:e, 'mlegacy', 'cat', NOW()) RETURNING id"
        ), {"e": event_id})).scalar_one()
        await s.commit()
        yield {"id": sig_id, "event_id": event_id}

        await s.execute(text("DELETE FROM signals WHERE id=:id"), {"id": sig_id})
        await s.execute(text("DELETE FROM events WHERE id=:e"), {"e": event_id})
        await s.commit()
```

- [ ] **Step 3: Run integration test (expect fail)**

```bash
docker compose exec app pytest tests/integration/test_signal_detail_api.py -v
```

Expected: FAIL (response missing new fields).

- [ ] **Step 4: Extend the signal detail handler**

Find the current signal-detail route (search for `@router.get("/signals/{` in `app/api/routes/`). Extend the handler to:
1. Load the signal with its `event_id`.
2. Query `event_news_links` joined to `news_clean` → `news` → `sources_registry` for the event, ordered by `relevance_score DESC NULLS LAST`, limited to 10.
3. Map to `SignalSourceOut`.
4. Build `timeline` as the same list mapped into `TimelineEventOut` (type="news").
5. Return the extended response including `reasoning`, `source_tier_mix`, `llm_model_version`, `sources`, `timeline`.

Example handler body (paste near existing detail route):

```python
from sqlalchemy import select
from sqlalchemy.orm import aliased
from app.api.schemas_v2 import SignalDetailOut, SignalSourceOut, TimelineEventOut
from app.db.models import Signal, EventNewsLink, NewsClean, News, SourceRegistry


@router.get("/signals/{signal_id}", response_model=SignalDetailOut)
async def get_signal_detail(signal_id: int, db: AsyncSession = Depends(get_db_session)):
    sig = (await db.execute(select(Signal).where(Signal.id == signal_id))).scalar_one_or_none()
    if sig is None:
        raise HTTPException(404, "signal not found")

    rows = (await db.execute(
        select(News, EventNewsLink, SourceRegistry)
        .join(NewsClean, NewsClean.news_id == News.id)
        .join(EventNewsLink, EventNewsLink.clean_id == NewsClean.id)
        .join(SourceRegistry, SourceRegistry.id == News.source_id, isouter=True)
        .where(EventNewsLink.event_id == sig.event_id)
        .order_by(EventNewsLink.relevance_score.desc().nulls_last())
        .limit(10)
    )).all()

    sources: list[SignalSourceOut] = []
    timeline: list[TimelineEventOut] = []
    for i, (n, link, sr) in enumerate(rows):
        sources.append(SignalSourceOut(
            news_id=n.id,
            title=n.title or "",
            url=n.url or "",
            source_name=(sr.source_name if sr else n.source_name) or "unknown",
            source_tier=(sr.tier if sr else n.source_tier) or 3,
            source_weight=(sr.weight if sr else n.source_weight),
            publish_date=n.publish_date.isoformat() if n.publish_date else None,
            excerpt=link.key_excerpt,
            relevance_score=link.relevance_score,
            role="primary" if i == 0 else "supporting",
        ))
        timeline.append(TimelineEventOut(
            at=n.publish_date.isoformat() if n.publish_date else "",
            source=(sr.source_name if sr else n.source_name) or "unknown",
            type="news",
            headline=n.title,
        ))

    # Build the base response using the existing mapper that the current detail route uses
    # (e.g. `app.api.signal_mapper.signal_to_detail_out(sig)`), then add the new fields.
    base = signal_to_detail_out(sig)  # existing helper, already in app/api/signal_mapper.py
    return base.model_copy(update={
        "reasoning": sig.reasoning,
        "llm_model_version": sig.llm_model_version,
        "source_tier_mix": sig.source_tier_mix,
        "sources": sources,
        "timeline": timeline,
    })
```

Merge the new fields into the **existing** handler — do not delete its current logic. Preserve the previous response shape; only add fields.

- [ ] **Step 5: Run integration tests**

```bash
docker compose exec app pytest tests/integration/test_signal_detail_api.py -v
```

Expected: PASS 2/2.

- [ ] **Step 6: Commit**

```bash
git add app/api/schemas_v2.py app/api/routes/ tests/integration/test_signal_detail_api.py tests/integration/conftest.py
git commit -m "feat(api): enrich GET /api/signals/{id} with sources, reasoning, timeline"
```

---

## Task 16: `GET /api/signals/{id}/sources` (lightweight endpoint)

**Files:**
- Modify: the signals route module from Task 15
- Test: extend `tests/integration/test_signal_detail_api.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_signal_detail_api.py`:

```python
@pytest.mark.asyncio
async def test_sources_only_endpoint(seeded_signal_with_three_sources):
    signal_id = seeded_signal_with_three_sources["id"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r = await client.get(f"/api/signals/{signal_id}/sources")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 3
    assert data == sorted(data, key=lambda s: -(s["relevance_score"] or 0))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec app pytest tests/integration/test_signal_detail_api.py::test_sources_only_endpoint -v
```

Expected: FAIL (404).

- [ ] **Step 3: Add the route**

Next to the `get_signal_detail` handler:

```python
@router.get("/signals/{signal_id}/sources", response_model=list[SignalSourceOut])
async def get_signal_sources(signal_id: int, db: AsyncSession = Depends(get_db_session)):
    sig = (await db.execute(select(Signal).where(Signal.id == signal_id))).scalar_one_or_none()
    if sig is None:
        raise HTTPException(404, "signal not found")
    # Reuse the same query shape used in get_signal_detail (factor into a helper if desired)
    rows = (await db.execute(
        select(News, EventNewsLink, SourceRegistry)
        .join(NewsClean, NewsClean.news_id == News.id)
        .join(EventNewsLink, EventNewsLink.clean_id == NewsClean.id)
        .join(SourceRegistry, SourceRegistry.id == News.source_id, isouter=True)
        .where(EventNewsLink.event_id == sig.event_id)
        .order_by(EventNewsLink.relevance_score.desc().nulls_last())
        .limit(10)
    )).all()
    return [
        SignalSourceOut(
            news_id=n.id, title=n.title or "", url=n.url or "",
            source_name=(sr.source_name if sr else n.source_name) or "unknown",
            source_tier=(sr.tier if sr else n.source_tier) or 3,
            source_weight=(sr.weight if sr else n.source_weight),
            publish_date=n.publish_date.isoformat() if n.publish_date else None,
            excerpt=link.key_excerpt,
            relevance_score=link.relevance_score,
            role="primary" if i == 0 else "supporting",
        )
        for i, (n, link, sr) in enumerate(rows)
    ]
```

- [ ] **Step 4: Run tests**

```bash
docker compose exec app pytest tests/integration/test_signal_detail_api.py -v
```

Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add app/api/routes/ tests/integration/test_signal_detail_api.py
git commit -m "feat(api): GET /api/signals/{id}/sources"
```

---

## Task 17: `GET /api/sources` — admin/debug endpoint

**Files:**
- Create: `app/api/routes/sources.py`
- Modify: `app/api/routes/__init__.py` (register router)
- Test: `tests/integration/test_sources_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_sources_api.py
"""GET /api/sources returns tier counts and 24h article counts."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_sources_list_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r = await client.get("/api/sources")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    for row in data:
        for k in ("source_name", "tier", "weight", "active", "source_type", "articles_24h", "signals_contributed_7d"):
            assert k in row
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec app pytest tests/integration/test_sources_api.py -v
```

Expected: FAIL (404).

- [ ] **Step 3: Implement the route**

```python
# app/api/routes/sources.py
"""Sources registry admin/debug endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db_session

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceStatsOut(BaseModel):
    source_name: str
    tier: int
    weight: float
    active: bool
    source_type: str
    articles_24h: int
    signals_contributed_7d: int


@router.get("", response_model=list[SourceStatsOut])
async def list_sources(db: AsyncSession = Depends(get_db_session)):
    rows = (await db.execute(text(
        """
        SELECT
          sr.source_name, sr.tier, sr.weight, sr.active, sr.source_type,
          COALESCE(
            (SELECT COUNT(*) FROM news n
             WHERE n.source_id = sr.id AND n.publish_date >= NOW() - INTERVAL '24 hours'),
            0
          ) AS articles_24h,
          COALESCE(
            (SELECT COUNT(DISTINCT s.id) FROM signals s
             JOIN event_news_links el ON el.event_id = s.event_id
             JOIN news_clean nc ON nc.id = el.clean_id
             JOIN news n ON n.id = nc.news_id
             WHERE n.source_id = sr.id AND s.created_at >= NOW() - INTERVAL '7 days'),
            0
          ) AS signals_contributed_7d
        FROM sources_registry sr
        WHERE sr.active = true
        ORDER BY sr.tier ASC, sr.source_name ASC
        """
    ))).mappings().all()
    return [SourceStatsOut(**r) for r in rows]
```

Register in `app/api/routes/__init__.py`:

```python
from app.api.routes import sources as _sources_routes  # add
api_router.include_router(_sources_routes.router)      # add
```

- [ ] **Step 4: Run test**

```bash
docker compose exec app pytest tests/integration/test_sources_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/api/routes/sources.py app/api/routes/__init__.py tests/integration/test_sources_api.py
git commit -m "feat(api): GET /api/sources admin/debug endpoint"
```

---

## Task 18: Frontend types for extended `Signal`

**Files:**
- Modify: `frontend/src/types/signal.ts`

- [ ] **Step 1: Read current file**

```bash
cat frontend/src/types/signal.ts
```

- [ ] **Step 2: Append/extend types**

Append to `frontend/src/types/signal.ts`:

```typescript
export type SignalSource = {
  news_id: number
  title: string
  url: string
  source_name: string
  source_tier: 1 | 2 | 3
  source_weight?: number | null
  publish_date: string | null
  excerpt: string | null
  relevance_score: number | null
  role: "primary" | "supporting"
}

export type TimelineEvent = {
  at: string
  source: string
  type: "news" | "market_move"
  headline?: string | null
  detail?: string | null
}
```

Update the existing `Signal` type to include:

```typescript
  reasoning?: string | null
  llm_model_version?: string | null
  source_tier_mix?: Record<string, number> | null
  sources?: SignalSource[]
  timeline?: TimelineEvent[]
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/signal.ts
git commit -m "feat(frontend): extend Signal type with reasoning, sources, timeline"
```

---

## Task 19: `<WhyThisMatters>` component

**Files:**
- Create: `frontend/src/components/signals/WhyThisMatters.tsx`
- Create: `frontend/src/components/signals/__tests__/WhyThisMatters.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/components/signals/__tests__/WhyThisMatters.test.tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { WhyThisMatters } from "../WhyThisMatters"

describe("WhyThisMatters", () => {
  it("renders reasoning and tier-mix badges", () => {
    render(
      <WhyThisMatters
        reasoning="Reuters Top News and BBC confirm the summit date, addressing the market resolution criteria directly."
        sourceTierMix={{ tier_1: 3, tier_2: 1 }}
      />,
    )
    expect(screen.getByText(/Reuters Top News and BBC confirm/)).toBeInTheDocument()
    expect(screen.getByText(/3 sources Tier 1/i)).toBeInTheDocument()
    expect(screen.getByText(/1 source Tier 2/i)).toBeInTheDocument()
  })

  it("hides when reasoning is null", () => {
    const { container } = render(<WhyThisMatters reasoning={null} sourceTierMix={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/signals/__tests__/WhyThisMatters.test.tsx
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement the component**

```typescript
// frontend/src/components/signals/WhyThisMatters.tsx
type Props = {
  reasoning: string | null | undefined
  sourceTierMix: Record<string, number> | null | undefined
}

function formatTierBadge(tier: string, count: number): string {
  const tierNum = tier.replace("tier_", "")
  const label = count === 1 ? "source" : "sources"
  return `${count} ${label} Tier ${tierNum}`
}

export function WhyThisMatters({ reasoning, sourceTierMix }: Props) {
  if (!reasoning) return null

  const entries = sourceTierMix
    ? Object.entries(sourceTierMix).filter(([, v]) => v > 0)
    : []

  return (
    <section
      aria-label="Pourquoi ça compte"
      className="rounded-xl border border-border bg-card p-4 sm:p-6 mb-4"
    >
      <header className="flex items-center gap-2 mb-2">
        <span aria-hidden>✨</span>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Pourquoi ça compte
        </h2>
      </header>
      <p className="text-base leading-relaxed">{reasoning}</p>
      {entries.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {entries.map(([tier, count]) => (
            <span
              key={tier}
              className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs"
            >
              {formatTierBadge(tier, count)}
            </span>
          ))}
        </div>
      )}
    </section>
  )
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npx vitest run src/components/signals/__tests__/WhyThisMatters.test.tsx
```

Expected: PASS 2/2.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/signals/WhyThisMatters.tsx frontend/src/components/signals/__tests__/WhyThisMatters.test.tsx
git commit -m "feat(frontend): WhyThisMatters component"
```

---

## Task 20: `<SourcesList>` component

**Files:**
- Create: `frontend/src/components/signals/SourcesList.tsx`
- Create: `frontend/src/components/signals/__tests__/SourcesList.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/components/signals/__tests__/SourcesList.test.tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import type { SignalSource } from "@/types/signal"
import { SourcesList } from "../SourcesList"

const sources: SignalSource[] = [
  {
    news_id: 1,
    title: "Trump confirms summit timing",
    url: "https://reuters.com/a",
    source_name: "Reuters",
    source_tier: 1,
    publish_date: new Date(Date.now() - 23 * 60 * 1000).toISOString(),
    excerpt: "summit confirmed for April 28",
    relevance_score: 0.9,
    role: "primary",
  },
  {
    news_id: 2,
    title: "Officials comment",
    url: "https://bbc.co.uk/a",
    source_name: "BBC",
    source_tier: 2,
    publish_date: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
    excerpt: null,
    relevance_score: 0.5,
    role: "supporting",
  },
]

describe("SourcesList", () => {
  it("renders count and items sorted by relevance", () => {
    render(<SourcesList sources={sources} />)
    expect(screen.getByText(/Sources \(2\)/i)).toBeInTheDocument()
    const links = screen.getAllByRole("link")
    expect(links[0]).toHaveAttribute("href", "https://reuters.com/a")
    expect(links[1]).toHaveAttribute("href", "https://bbc.co.uk/a")
  })

  it("renders excerpt with quotation marks when present", () => {
    render(<SourcesList sources={sources} />)
    expect(screen.getByText(/« summit confirmed for April 28 »/)).toBeInTheDocument()
  })

  it("renders nothing when empty", () => {
    const { container } = render(<SourcesList sources={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/signals/__tests__/SourcesList.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement the component**

```typescript
// frontend/src/components/signals/SourcesList.tsx
import { formatDistanceToNow } from "date-fns"
import { fr } from "date-fns/locale"
import type { SignalSource } from "@/types/signal"

type Props = {
  sources: SignalSource[]
}

const tierBadgeClass: Record<1 | 2 | 3, string> = {
  1: "bg-green-100 text-green-900",
  2: "bg-amber-100 text-amber-900",
  3: "bg-gray-100 text-gray-800",
}

export function SourcesList({ sources }: Props) {
  if (!sources || sources.length === 0) return null
  const sorted = [...sources].sort(
    (a, b) => (b.relevance_score ?? 0) - (a.relevance_score ?? 0),
  )

  return (
    <section aria-label="Sources" className="rounded-xl border border-border bg-card p-4">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
        Sources ({sorted.length})
      </h3>
      <ul className="flex flex-col gap-3">
        {sorted.map((s) => {
          const rel = s.publish_date
            ? formatDistanceToNow(new Date(s.publish_date), { addSuffix: true, locale: fr })
            : ""
          return (
            <li key={s.news_id}>
              <a
                href={s.url}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Lire l'article sur ${s.source_name}`}
                className="block rounded-lg p-3 hover:bg-muted/60 transition-colors"
              >
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{s.source_name}</span>
                  {rel && <span>· {rel}</span>}
                  <span
                    className={`ml-auto rounded-full px-2 py-0.5 text-[10px] font-semibold ${tierBadgeClass[s.source_tier]}`}
                  >
                    T{s.source_tier}
                  </span>
                </div>
                <div className="mt-1 text-sm font-medium">{s.title}</div>
                {s.excerpt && (
                  <div className="mt-1 text-sm italic text-muted-foreground">
                    « {s.excerpt} »
                  </div>
                )}
              </a>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npx vitest run src/components/signals/__tests__/SourcesList.test.tsx
```

Expected: PASS 3/3.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/signals/SourcesList.tsx frontend/src/components/signals/__tests__/SourcesList.test.tsx
git commit -m "feat(frontend): SourcesList component with clickable articles"
```

---

## Task 21: `<SignalTimeline>` component

**Files:**
- Create: `frontend/src/components/signals/SignalTimeline.tsx`
- Create: `frontend/src/components/signals/__tests__/SignalTimeline.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/components/signals/__tests__/SignalTimeline.test.tsx
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import type { TimelineEvent } from "@/types/signal"
import { SignalTimeline } from "../SignalTimeline"

const events: TimelineEvent[] = Array.from({ length: 10 }).map((_, i) => ({
  at: new Date(2026, 3, 23, 14, i * 3).toISOString(),
  source: `Source ${i}`,
  type: "news",
  headline: `Event ${i}`,
}))

describe("SignalTimeline", () => {
  it("shows first 8 items and a voir plus toggle", () => {
    render(<SignalTimeline events={events} />)
    expect(screen.getAllByRole("listitem")).toHaveLength(8)
    expect(screen.getByRole("button", { name: /voir plus/i })).toBeInTheDocument()
  })

  it("reveals remaining items on voir plus", () => {
    render(<SignalTimeline events={events} />)
    fireEvent.click(screen.getByRole("button", { name: /voir plus/i }))
    expect(screen.getAllByRole("listitem")).toHaveLength(10)
  })

  it("renders nothing when empty", () => {
    const { container } = render(<SignalTimeline events={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/signals/__tests__/SignalTimeline.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement the component**

```typescript
// frontend/src/components/signals/SignalTimeline.tsx
import { useState } from "react"
import type { TimelineEvent } from "@/types/signal"

type Props = { events: TimelineEvent[] }

const MAX_VISIBLE = 8

function bulletClass(type: TimelineEvent["type"]): string {
  if (type === "market_move") return "bg-emerald-500"
  return "bg-blue-500"
}

function formatTime(iso: string): string {
  if (!iso) return ""
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ""
  return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
}

export function SignalTimeline({ events }: Props) {
  const [expanded, setExpanded] = useState(false)
  if (!events || events.length === 0) return null
  const sorted = [...events].sort((a, b) => a.at.localeCompare(b.at))
  const visible = expanded ? sorted : sorted.slice(0, MAX_VISIBLE)

  return (
    <section aria-label="Chronologie" className="rounded-xl border border-border bg-card p-4">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
        Chronologie
      </h3>
      <ul className="flex flex-col gap-2">
        {visible.map((e, idx) => (
          <li key={`${e.at}-${idx}`} className="flex items-start gap-3 text-sm">
            <span className="mt-1 w-[48px] shrink-0 text-xs text-muted-foreground">
              {formatTime(e.at)}
            </span>
            <span className={`mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full ${bulletClass(e.type)}`} />
            <span className="flex-1">
              <span className="font-medium">{e.source}</span>
              {e.headline ? <span> — {e.headline}</span> : null}
              {e.detail ? <span className="text-muted-foreground"> {e.detail}</span> : null}
            </span>
          </li>
        ))}
      </ul>
      {sorted.length > MAX_VISIBLE && !expanded && (
        <button
          type="button"
          className="mt-3 text-xs text-primary underline"
          onClick={() => setExpanded(true)}
        >
          Voir plus ({sorted.length - MAX_VISIBLE})
        </button>
      )}
    </section>
  )
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npx vitest run src/components/signals/__tests__/SignalTimeline.test.tsx
```

Expected: PASS 3/3.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/signals/SignalTimeline.tsx frontend/src/components/signals/__tests__/SignalTimeline.test.tsx
git commit -m "feat(frontend): SignalTimeline component"
```

---

## Task 22: Integrate the three components into `SignalDetail.tsx`

**Files:**
- Modify: `frontend/src/pages/SignalDetail.tsx`
- Modify: `frontend/src/lib/api/signals.ts` (if needed — ensure it returns `sources`, `timeline`, `reasoning`)

- [ ] **Step 1: Verify the API client surface**

```bash
cat frontend/src/lib/api/signals.ts
```

If the returned `Signal` type doesn't already include the new fields (it should, via the type extension in Task 18), no change is needed. If there's any field filtering, remove it so `sources`, `timeline`, `reasoning`, `source_tier_mix` pass through.

- [ ] **Step 2: Edit `SignalDetail.tsx`**

Add imports at the top:

```typescript
import { WhyThisMatters } from "@/components/signals/WhyThisMatters"
import { SourcesList } from "@/components/signals/SourcesList"
import { SignalTimeline } from "@/components/signals/SignalTimeline"
```

Place components according to the spec's integration order:
1. Market header (existing)
2. `<WhyThisMatters reasoning={signal.reasoning} sourceTierMix={signal.source_tier_mix} />`
3. `<OrderForm />` (existing)
4. Two-column grid: left = `<ScoreBreakdown>` (existing), right = `<SourcesList sources={signal.sources ?? []} />`
5. `<SignalTimeline events={signal.timeline ?? []} />` (full-width)
6. Footer (existing)

- [ ] **Step 3: Manual smoke test**

```bash
cd frontend && npm run dev
```

Open a signal detail page in the browser. Confirm the three new sections render for a post-Axis-A signal (one with `reasoning`) and auto-hide for legacy signals.

- [ ] **Step 4: TypeScript + build check**

```bash
cd frontend && npx tsc --noEmit && npm run build
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SignalDetail.tsx frontend/src/lib/api/signals.ts
git commit -m "feat(frontend): wire WhyThisMatters, SourcesList, SignalTimeline into SignalDetail"
```

---

## Task 23: Playwright smoke test on `/signals/:id`

**Files:**
- Create: `frontend/tests/e2e/signal-detail.spec.ts`

- [ ] **Step 1: Write the test**

```typescript
// frontend/tests/e2e/signal-detail.spec.ts
import { expect, test } from "@playwright/test"

test("post-Axis-A signal detail shows reasoning, sources, timeline", async ({ page }) => {
  await page.goto("/signals/1")
  await expect(page.getByRole("heading", { name: /pourquoi ça compte/i })).toBeVisible({ timeout: 10_000 })
  await expect(page.getByRole("heading", { name: /sources \(/i })).toBeVisible()
  await expect(page.getByRole("heading", { name: /chronologie/i })).toBeVisible()
})
```

Configure or confirm an existing post-Axis-A signal exists in the dev DB — or seed one as part of the test setup.

- [ ] **Step 2: Run**

```bash
cd frontend && npx playwright test tests/e2e/signal-detail.spec.ts
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/e2e/signal-detail.spec.ts
git commit -m "test(e2e): signal detail shows three new sections"
```

---

## Task 24: Legacy backfill script

**Files:**
- Create: `scripts/backfill_reasoning.py`

- [ ] **Step 1: Write the script**

```python
# scripts/backfill_reasoning.py
"""One-off: backfill `reasoning` + `source_tier_mix` for pre-Axis-A signals.

Usage:
    docker compose exec app python -m scripts.backfill_reasoning --days 7 --dry-run
    docker compose exec app python -m scripts.backfill_reasoning --days 7
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.database import get_async_session_factory
from app.db.models import EventNewsLink, News, NewsClean, Signal, SourceRegistry
from app.llm.reasoning_analyzer import create_reasoning_analyzer
from app.signal.signal_builder import build_signal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main(days: int, dry_run: bool) -> None:
    analyzer = create_reasoning_analyzer()
    session_factory = get_async_session_factory()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with session_factory() as s:
        rows = (await s.execute(
            select(Signal).where(
                Signal.reasoning.is_(None),
                Signal.created_at >= cutoff,
            ).order_by(Signal.created_at.desc())
        )).scalars().all()

    logger.info("backfill: candidates=%d dry_run=%s", len(rows), dry_run)
    for sig in rows:
        async with session_factory() as s:
            arts_rows = (await s.execute(
                select(News, NewsClean, EventNewsLink, SourceRegistry)
                .join(NewsClean, NewsClean.news_id == News.id)
                .join(EventNewsLink, EventNewsLink.clean_id == NewsClean.id)
                .join(SourceRegistry, SourceRegistry.id == News.source_id, isouter=True)
                .where(EventNewsLink.event_id == sig.event_id)
                .limit(5)
            )).all()

        articles = [
            {
                "news_clean_id": nc.id,
                "title": n.title or "",
                "source_name": (sr.source_name if sr else n.source_name) or "unknown",
                "source_tier": (sr.tier if sr else n.source_tier) or 3,
                "clean_text": nc.clean_text or "",
                "publish_date": n.publish_date.isoformat() if n.publish_date else None,
            }
            for (n, nc, _, sr) in arts_rows
        ]
        if not articles:
            continue

        if dry_run:
            logger.info("[dry-run] would backfill signal id=%s", sig.id)
            continue

        result = await build_signal(
            event={"id": sig.event_id, "title": "(legacy)", "summary": ""},
            market={"id": sig.market_id, "question": "(legacy)", "price": 0.5},
            articles=articles,
            analyzer=analyzer,
            persist=False,
        )
        if result is None:
            logger.info("backfill: rejected id=%s", sig.id)
            continue

        async with session_factory() as s:
            s.add(sig)
            merged = await s.merge(sig)
            merged.reasoning = result["reasoning"]
            merged.llm_model_version = result["llm_model_version"]
            merged.source_tier_mix = result["source_tier_mix"]
            await s.commit()
        logger.info("backfill: filled id=%s", sig.id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.days, args.dry_run))
```

- [ ] **Step 2: Smoke-run in dry-run mode**

```bash
docker compose exec app python -m scripts.backfill_reasoning --days 7 --dry-run
```

Expected: log lines `[dry-run] would backfill signal id=...` for pre-Axis-A signals.

- [ ] **Step 3: Commit**

```bash
git add scripts/backfill_reasoning.py
git commit -m "feat(scripts): backfill_reasoning for legacy pre-Axis-A signals"
```

---

## Final Verification

- [ ] **Step 1: Run the full test suite**

```bash
docker compose exec app pytest tests/unit tests/integration -x --tb=short
```

Expected: all tests pass.

- [ ] **Step 2: Run the frontend tests and build**

```bash
cd frontend && npx vitest run && npx tsc --noEmit && npm run build
```

Expected: all PASS, zero TypeScript errors, build succeeds.

- [ ] **Step 3: Apply all migrations in a clean DB one more time to ensure order works end-to-end**

```bash
docker compose exec app alembic downgrade 013
docker compose exec app alembic upgrade head
```

Expected: clean downgrade/upgrade cycle.

- [ ] **Step 4: End-to-end manual smoke**

1. Restart workers: `docker compose restart app celery-beat celery-worker-ingestion celery-worker-scoring`.
2. Wait for a new signal to be produced (or trigger `fetch_gdelt` + a scoring cycle manually).
3. Open that signal's detail page in the browser.
4. Confirm `<WhyThisMatters>`, `<SourcesList>`, `<SignalTimeline>` render with real data.
5. Confirm each source item opens the article in a new tab.

---

## Post-Axis-A Invariants (ops checklist)

- Every new signal row has `reasoning` NOT NULL and ≥ 100 chars.
- Every new signal has ≥ 1 `event_news_links` row with `key_excerpt` NOT NULL for its event.
- Every `key_excerpt` appears verbatim in the corresponding `news_clean.clean_text`.
- `signals_pending_reasoning` stays near 0 under normal quota conditions.
- `GET /api/sources` returns non-zero `articles_24h` for all tier-1 sources.

If any of these breaks in production: tail `signals.rejected_no_reasoning` / `signals.rejected_no_excerpts` / `llm.quota_exceeded` log counters for the root cause.
