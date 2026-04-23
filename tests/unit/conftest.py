"""Shared async DB fixtures for unit tests that hit Postgres.

`app.db.database.get_session_factory()` caches on PID only, which breaks
pytest-asyncio's per-function event loops. These fixtures give each test a
fresh engine bound to the current loop and dispose it cleanly on teardown.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


@pytest.fixture
async def async_db_engine():
    """Per-test async engine bound to the current event loop. Disposed on teardown."""
    engine = create_async_engine(get_settings().database_url, echo=False)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def async_db_factory(async_db_engine):
    """Per-test async session factory built on the per-test engine."""
    return async_sessionmaker(async_db_engine, class_=AsyncSession, expire_on_commit=False)
