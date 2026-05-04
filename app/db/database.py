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
    on its first DB call. Diagnosed 2026-05-04 after a 6-day outage where
    worker-pipeline crashed silently every ~5 min via `task_time_limit`.

Pre-2026-05-04 the check was PID-only, which masked the problem until
Celery fired enough tasks per worker boot for cross-loop reuse to
surface. The combination of the bigger backlog post-Filter-A change and
the gpt-4o → gpt-4o-mini deploy increased task throughput per boot,
which exposed the bug constantly instead of intermittently.
"""

import asyncio
import os
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()

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
        # We do NOT call `_engine.dispose()` on the stale engine: the
        # asyncpg connections it owns are bound to a loop that's already
        # closed, so the dispose call would itself raise the cross-loop
        # error. We let the GC reclaim it; SQLAlchemy + asyncpg handle
        # zombie pools without leaking sockets in our footprint.
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.is_development,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
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
