"""news_clean.simhash INTEGER → BIGINT (close model/schema drift)

Revision ID: 031
Revises: 030
Create Date: 2026-05-06

Live cutover bug 2026-05-05 (production go-live for yourforesight.com):
the SQLAlchemy model in `app/db/models.py` declared
`simhash: Mapped[Optional[int]] = mapped_column(BigInteger)`, but the
column actually shipped as PostgreSQL `integer` (int32, max
2_147_483_647). The original migration that created `news_clean`
(probably 001_initial_schema.py back when this codebase was much
smaller) used `Integer` — and the drift was never caught because
SimHash collisions in dev with fewer articles rarely produced the
> int32 values that the live RSS feed mix triggered immediately.

Symptom: every `process_article` task crashed at the
`INSERT INTO news_clean ... VALUES ($3::BIGINT, ...)` step with

    asyncpg.exceptions.NumericValueOutOfRangeError: integer out of range

…because PostgreSQL evaluated the cast against the actual column type
(int32) on row insert, even though SQLAlchemy emitted `$3::BIGINT` in
the prepared statement. 100 % of news ingestion was blocked. Pipeline
end-to-end blocked → 0 events, 0 signals.

Live fix on prod was an inline `ALTER TABLE ... ALTER COLUMN simhash
TYPE bigint;` — completed in milliseconds because the table only
held a handful of rows after the cutover. This migration formalises
that fix so any fresh deploy applies it automatically on
`alembic upgrade head` (the docker-compose `app` entrypoint runs that
on boot).

ALTER COLUMN ... TYPE bigint takes an `ACCESS EXCLUSIVE` lock briefly
while it rewrites the column. On a populated table (e.g. after months
of ingestion) this could block readers/writers for the rewrite
duration. The MIGRATION_SAFETY.md runbook flags this; for a small DB
the cost is negligible. If you re-run this on a multi-million-row
news_clean, prefer the two-step pattern:
   1. ADD COLUMN simhash_new bigint;
   2. UPDATE … SET simhash_new = simhash; (in batches)
   3. DROP COLUMN simhash; RENAME COLUMN simhash_new TO simhash;
…outside of Alembic so the lock window is bounded.
"""

from __future__ import annotations

from alembic import op


revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE news_clean ALTER COLUMN simhash TYPE bigint")


def downgrade() -> None:
    # Lossy — values >= 2^31 would silently truncate. The downgrade is
    # provided for completeness but should NOT be run on real data.
    op.execute("ALTER TABLE news_clean ALTER COLUMN simhash TYPE integer")
