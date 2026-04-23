import pytest
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.db.database as _db_mod
from app.core.config import get_settings


# Base de données SQLite en mémoire pour les tests
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# Async Postgres fixtures — shared by unit + integration tests.
#
# `app.db.database.get_session_factory()` caches on PID only, which breaks
# pytest-asyncio's per-function event loops. These fixtures give each test
# a fresh engine bound to the current loop and dispose it cleanly on teardown.
# ---------------------------------------------------------------------------
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


@pytest.fixture(autouse=True)
def _reset_db_cache():
    """Force app.db.database to rebuild engine/factory per test to match pytest-asyncio's per-function loops."""
    _db_mod._engine = None
    _db_mod._session_factory = None
    _db_mod._owner_pid = None
    yield


# Mock OpenAI sans appel réseau
@pytest.fixture
def mock_openai():
    mock = MagicMock()
    mock.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"summary": "Test summary", "impact": "high"}'
                    )
                )
            ]
        )
    )
    return mock


# Objet Market de test
@pytest.fixture
def sample_market():
    return {
        "market_id": "test-market-001",
        "question": "Will BTC reach 100k?",
        "category": "crypto",
        "liquidity": 50000.0,
        "volume_24h": 10000.0,
        "best_bid": 0.45,
        "best_ask": 0.55,
        "spread": 0.10,
    }


# Objet News de test
@pytest.fixture
def sample_news():
    return {
        "url": "https://reuters.com/test-article",
        "title": "Test Breaking News",
        "content": "This is a test article with enough words to pass quality filters.",
        "source": "reuters",
        "source_tier": 1,
        "source_weight": 1.0,
        "language": "en",
    }


# Objet EventFromNews de test
@pytest.fixture
def sample_event():
    return {
        "title": "Test Event",
        "summary": "A test event generated from news",
        "key_entities": ["Bitcoin", "USD"],
        "bucket": "crypto",
        "source_count": 2,
    }
