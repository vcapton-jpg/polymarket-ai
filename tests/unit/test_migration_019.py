"""Vérifie que migration 019 crée les 5 tables attendues avec les colonnes critiques."""

from __future__ import annotations
import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


def _make_engine():
    """Create a fresh async engine to avoid event-loop conflicts."""
    settings = get_settings()
    return create_async_engine(settings.database_url, echo=False)


@pytest.mark.asyncio
async def test_migration_019_creates_tables():
    engine = _make_engine()
    try:
        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
    finally:
        await engine.dispose()

    expected = {
        "user_limits",
        "paper_positions",
        "onboarding_progress",
        "quiz_attempts",
        "outcome_views",
    }
    missing = expected - set(tables)
    assert not missing, f"Tables manquantes: {missing}"


@pytest.mark.asyncio
async def test_user_limits_has_budget_columns():
    engine = _make_engine()
    try:
        async with engine.connect() as conn:
            cols_info = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_columns("user_limits")
            )
    finally:
        await engine.dispose()
    cols = {c["name"] for c in cols_info}

    required = {
        "user_id", "budget_weekly_eur", "max_stake_eur", "level",
        "real_trades_count", "consecutive_losses", "cooloff_until",
        "quiz_passed", "age_confirmed_18", "cgu_accepted_at",
    }
    missing = required - cols
    assert not missing, f"Colonnes manquantes: {missing}"
