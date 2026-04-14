"""Database base and engine setup.

The engine and session factory are created lazily per-process so that
Celery fork workers get their own asyncpg connection pool bound to their
own event loop (avoids "Future attached to a different loop" errors).
"""

import os

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()

_engine: AsyncEngine | None = None
_session_factory = None
_owner_pid: int | None = None


def _get_engine() -> AsyncEngine:
    global _engine, _owner_pid
    pid = os.getpid()
    if _engine is None or _owner_pid != pid:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.is_development,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        _owner_pid = pid
    return _engine


def get_session_factory():
    global _session_factory, _owner_pid
    pid = os.getpid()
    if _session_factory is None or _owner_pid != pid:
        _get_engine()
        _session_factory = sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


engine = _get_engine()
async_session_factory = get_session_factory()


async def get_db_session() -> AsyncSession:
    """Get async database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session