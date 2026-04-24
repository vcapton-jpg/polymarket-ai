"""Migration 025 — data-only rename of SignalPrediction.variant column values.

Chantier #5 renames the legacy variant name 'signal' (written by chantier #1's
record_baselines) to 'heuristic_v1' so the heuristic is first-class alongside
baseline_* and any future shadow variants.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_no_signal_variant_rows_remain_after_upgrade(async_db_factory):
    """After migration 025, no 'signal' rows exist in signal_predictions."""
    async with async_db_factory() as s:
        count = (await s.execute(
            text("SELECT COUNT(*) FROM signal_predictions WHERE variant = 'signal'")
        )).scalar_one()
        assert count == 0, (
            f"Migration 025 leaves {count} 'signal' rows; expected 0. "
            "Re-run `alembic upgrade head` against the test database."
        )


@pytest.mark.asyncio
async def test_heuristic_v1_rows_present_when_signals_existed(async_db_factory):
    """Dev DB carries pre-migration data → heuristic_v1 rows now exist.

    Tolerant: if the DB is empty (e.g. fresh CI), the count can be 0.
    """
    async with async_db_factory() as s:
        total_preds = (await s.execute(
            text("SELECT COUNT(*) FROM signal_predictions")
        )).scalar_one()
        if total_preds == 0:
            pytest.skip("signal_predictions empty — nothing to rename")
        heuristic = (await s.execute(
            text("SELECT COUNT(*) FROM signal_predictions WHERE variant = 'heuristic_v1'")
        )).scalar_one()
        assert heuristic > 0, "Expected at least one heuristic_v1 row post-migration"


@pytest.mark.asyncio
async def test_check_constraint_if_present_allows_heuristic_v1(async_db_factory):
    """Variant check constraint (if any) must allow 'heuristic_v1' and 'heuristic_shadow'.

    We insert a probe row under a rollback-able SAVEPOINT; the assertion is
    'no CheckViolationError', and the row never escapes the transaction.

    We use an existing signal id so the foreign-key constraint doesn't mask
    the check we actually care about. If the DB has no signals, we skip.
    """
    from sqlalchemy.exc import IntegrityError

    async with async_db_factory() as s:
        signal_id = (await s.execute(
            text("SELECT id FROM signals LIMIT 1")
        )).scalar_one_or_none()
        if signal_id is None:
            pytest.skip("no signals in DB — cannot probe signal_predictions variant")

        # probe values that exercise any possible CHECK constraint
        try:
            async with s.begin_nested():
                await s.execute(text(
                    "INSERT INTO signal_predictions (signal_id, variant, predicted_probability) "
                    "VALUES (:sid, 'heuristic_v1', 0.5)"
                ), {"sid": signal_id})
                await s.execute(text(
                    "INSERT INTO signal_predictions (signal_id, variant, predicted_probability) "
                    "VALUES (:sid, 'heuristic_shadow', 0.5)"
                ), {"sid": signal_id})
                raise Exception("rollback")  # always rollback the savepoint
        except IntegrityError as exc:
            # CHECK constraint violation on variant would land here and must fail the test
            if "check" in str(exc).lower() and "variant" in str(exc).lower():
                raise
            # any other IntegrityError (e.g. unique) means the CHECK passed — tolerate
        except Exception as exc:
            if str(exc) != "rollback":
                raise
