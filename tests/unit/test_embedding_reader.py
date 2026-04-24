"""Unit tests for embedding_reader — flag-driven column routing."""

from __future__ import annotations

import pytest

from app.processing.embedding_reader import (
    active_column_name,
    get_active_embedding,
)


class _Row:
    """Minimal stand-in for an ORM row."""
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def test_get_active_embedding_v1_returns_embedding(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_VARIANT_NEWS", "v1")
    from app.core.config import get_settings
    get_settings.cache_clear()
    row = _Row(embedding=[1.0, 2.0], embedding_v2=[9.0])
    assert get_active_embedding(row, "news") == [1.0, 2.0]


def test_get_active_embedding_v2_returns_embedding_v2(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_VARIANT_NEWS", "v2")
    from app.core.config import get_settings
    get_settings.cache_clear()
    row = _Row(embedding=[1.0, 2.0], embedding_v2=[9.0])
    assert get_active_embedding(row, "news") == [9.0]


def test_get_active_embedding_returns_none_if_column_is_none(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_VARIANT_NEWS", "v2")
    from app.core.config import get_settings
    get_settings.cache_clear()
    row = _Row(embedding=[1.0, 2.0], embedding_v2=None)
    assert get_active_embedding(row, "news") is None


def test_get_active_embedding_invalid_surface_raises():
    row = _Row(embedding=[1.0])
    with pytest.raises(ValueError, match="surface"):
        get_active_embedding(row, "nonsense")


def test_active_column_name_returns_literal_for_v1_and_v2(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_VARIANT_MARKET", "v1")
    from app.core.config import get_settings
    get_settings.cache_clear()
    assert active_column_name("market") == "embedding"
    monkeypatch.setenv("EMBEDDINGS_VARIANT_MARKET", "v2")
    get_settings.cache_clear()
    assert active_column_name("market") == "embedding_v2"


def test_active_column_name_invalid_surface_raises():
    with pytest.raises(ValueError, match="surface"):
        active_column_name("nonsense")


def test_active_column_name_whitelist_is_closed():
    """Must not accept arbitrary identifiers — SQL-injection hardening."""
    with pytest.raises(ValueError):
        active_column_name("news; DROP TABLE users; --")
