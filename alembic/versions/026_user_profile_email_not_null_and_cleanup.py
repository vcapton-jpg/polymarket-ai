"""Cleanup orphan UserProfile rows + tighten user_profiles.email to NOT NULL.

Revision ID: 026
Revises: 025
Create Date: 2026-04-27

Audit P1-3 follow-through. The pre-2026-04-27 `_get_or_create_portfolio`
in `app/api/routes/trading.py` (fixed in PR #13) used to create a
`UserProfile(plan="free")` row with no email and no link to the
authenticated caller every time the endpoint was hit. Those rows still
sit in the DB; the post-fix code ignores them but they violate the
implicit invariant that every UserProfile is an auth identity.

This migration runs in three safe phases:

1. Delete UserProfile rows with NULL email **only when** they have no
   dependent rows in any of the eight CASCADE tables. Anything with
   data attached is preserved.

2. For surviving NULL-email rows (data attached → can't delete) we
   write a synthetic `orphan-{id}@invalid.local` so the NOT NULL
   constraint can be enforced. `.invalid.local` is non-routable per
   RFC 6761 §6.4 so the address can never collide with a real signup.

3. `ALTER TABLE … SET NOT NULL` on `user_profiles.email`.

The migration is idempotent — re-running on an already-migrated DB is
a no-op (DELETE affects 0 rows, UPDATE affects 0 rows, ALTER is a
catalog-level set that PostgreSQL silently accepts when already set).
"""

from __future__ import annotations

from alembic import op


revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Phase 1 — safe orphan deletion. The eight tables below cover every
    # FK to user_profiles.id at 2026-04-27. CASCADE on the FKs means
    # `DELETE FROM user_profiles WHERE id = X` would also drop dependent
    # rows; we want the opposite — *don't* delete anyone whose id is
    # referenced anywhere.
    op.execute(
        """
        DELETE FROM user_profiles
        WHERE email IS NULL
          AND id NOT IN (SELECT DISTINCT user_id FROM portfolios)
          AND id NOT IN (SELECT DISTINCT user_id FROM api_keys_b2b)
          AND id NOT IN (SELECT DISTINCT user_id FROM user_limits)
          AND id NOT IN (SELECT DISTINCT user_id FROM paper_positions)
          AND id NOT IN (SELECT DISTINCT user_id FROM onboarding_progress)
          AND id NOT IN (SELECT DISTINCT user_id FROM quiz_attempts)
          AND id NOT IN (SELECT DISTINCT user_id FROM outcome_views)
          AND id NOT IN (
              SELECT DISTINCT user_id FROM daily_briefs WHERE user_id IS NOT NULL
          )
        """
    )

    # Phase 2 — surviving NULL-email rows have data attached; we cannot
    # destroy that data, so we backfill a synthetic non-routable email
    # so the NOT NULL constraint can land. Operators can later audit
    # these rows by `email LIKE 'orphan-%@invalid.local'`.
    op.execute(
        """
        UPDATE user_profiles
        SET email = 'orphan-' || id || '@invalid.local'
        WHERE email IS NULL
        """
    )

    # Phase 3 — enforce the invariant in the schema.
    op.execute("ALTER TABLE user_profiles ALTER COLUMN email SET NOT NULL")


def downgrade() -> None:
    # Drop the NOT NULL constraint. The deleted orphans cannot be
    # restored; the synthesized `orphan-…@invalid.local` rows stay as
    # they are (nothing meaningful to roll them back to).
    op.execute("ALTER TABLE user_profiles ALTER COLUMN email DROP NOT NULL")
