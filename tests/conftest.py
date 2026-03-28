import pytest
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# Base de données SQLite en mémoire pour les tests
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


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
