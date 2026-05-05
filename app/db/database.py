"""Database base and engine setup.

The engine and session factory are created lazily and tracked by both
**process id** AND **event-loop id** so Celery workers using
`--pool=solo` get a fresh asyncpg connection pool bound to whichever
event loop the current task is running in.

Why both:
  * `os.getpid()` covers the post-fork case (Celery prefork pool, FastAPI
    workers spawned by uvicorn).
  * `id(asyncio.get_running_loop())` covers the **same-PID, different-loop**
    case that Celery `--pool=solo` produces: each task is wrapped in its
    own `asyncio.run(...)` call which creates a fresh loop, runs the
    coroutine, then closes. Without the loop check the global pool
    stays bound to the very first loop a worker ever saw, and any
    subsequent task hits a
        `RuntimeError: got Future <Future …> attached to a different loop`
    on its first DB call. Diagnosed 2026-05-04 after a 6-day outage.

Why NullPool everywhere:
  Celery `--pool=solo` runs each task in its own `asyncio.run(...)`,
  which closes the loop on exit. The asyncpg connections held by the
  previous engine cannot be closed cleanly afterwards (their `await
  conn.close()` would re-enter the dead loop and raise). So every loop
  switch leaks the entire pool — 10 base + 20 overflow = 30 zombie
  connections × ~30 KB each = ~1 MB per task. After 1500 tasks the
  worker reaches the 1.5 GB Docker memory limit and the kernel SIGKILLs
  it (exit 137). That's the OOM crash loop diagnosed 2026-05-05 — Docker
  events report `oom` even though `docker inspect` says `OOMKilled:false`
  (a known Docker-Desktop-on-macOS attribution bug).

  NullPool eliminates pooling entirely: each session opens its own
  asyncpg connection and closes it on `__aexit__`. Trade-off:
    + No persistent state across loops → no leak, no OOM
    + Simple, no special cleanup logic
    - +2-3 ms per session for the TCP handshake (negligible at our
      throughput; pipeline tasks dominate at >100 ms each)

  For uvicorn + FastAPI the trade-off is identical because we run a
  single uvicorn worker per app container and FastAPI requests are
  short-lived. If we ever scale to many concurrent uvicorn workers we
  can switch FastAPI back to a pooled engine; Celery will keep
  NullPool.
"""

import asyncio
import os
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()


# Echo opt-in via env var, default OFF — never tied to `is_development`.
#
# Why: `echo=True` makes SQLAlchemy log every statement *and its bind
# parameters*. For our `news_clean` INSERT that includes the 1536-dim
# embedding rendered as a JSON string, the bound row is ~30 KB *per
# article* and the log line is emitted twice (the engine logger plus
# Celery's MainProcess re-emit). At our ingestion rate (~50 articles
# per pipeline-task burst) that's ~3 MB of log buffer churn per task.
# Python's logging handlers + asyncio's task bookkeeping buffer those
# strings before they hit the docker JSON-file driver, the GC can't
# free them fast enough, and the worker's RSS climbs from 100 MB to
# 2.7 GB in ~7 minutes — straight into the 3 GB ceiling and OOM-kill.
#
# Diagnosed 2026-05-05 from worker-pipeline-2 logs: a single
# `process_article` task printed an INSERT statement whose `$7` bind
# parameter was a vector(1536) text rendering of 29,088 chars, twice.
# `VmPeak` had hit 3.92 GB on a 3 GB-limited container — definitive
# OOM-kill, not Docker-Desktop attribution noise.
#
# Disabling echo by default kills that buffer pressure outright. The
# `DB_ECHO=1` env var is the dev-time escape hatch when someone really
# does want SQL trace; nobody should be running it on a worker in
# steady state.
_DB_ECHO = os.environ.get("DB_ECHO", "").lower() in ("1", "true", "yes")

_engine: AsyncEngine | None = None
_session_factory = None
_owner_pid: int | None = None
_owner_loop_id: int | None = None


def _current_loop_id() -> Optional[int]:
    """Return id() of the currently-running event loop, or None at import
    time / sync-context call sites where no loop is active yet."""
    try:
        return id(asyncio.get_running_loop())
    except RuntimeError:
        return None


def _get_engine() -> AsyncEngine:
    global _engine, _owner_pid, _owner_loop_id
    pid = os.getpid()
    loop_id = _current_loop_id()
    if (
        _engine is None
        or _owner_pid != pid
        or (loop_id is not None and _owner_loop_id != loop_id)
    ):
        # NullPool: open + close a fresh asyncpg connection per session.
        # See module docstring for the OOM-cause analysis. We still
        # leak the previous `_engine` Python object on a loop switch,
        # but that's just SQLAlchemy bookkeeping (~30 KB) — no native
        # sockets attached to it because NullPool never opened any.
        _engine = create_async_engine(
            settings.database_url,
            echo=_DB_ECHO,
            poolclass=NullPool,
        )
        _owner_pid = pid
        _owner_loop_id = loop_id
    return _engine


def get_session_factory():
    global _session_factory, _owner_pid, _owner_loop_id
    pid = os.getpid()
    loop_id = _current_loop_id()
    if (
        _session_factory is None
        or _owner_pid != pid
        or (loop_id is not None and _owner_loop_id != loop_id)
    ):
        _get_engine()
        _session_factory = sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


# Import-time engine warm-up. The factory is rebuilt automatically on
# first use inside any async task that runs in a different loop, so this
# is purely a convenience for sync callers (CLI scripts, tests) that
# don't open a loop before reaching the first DB call.
engine = _get_engine()
async_session_factory = get_session_factory()


async def get_db_session() -> AsyncSession:
    """Get async database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
