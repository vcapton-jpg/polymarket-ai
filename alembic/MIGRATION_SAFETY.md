# Alembic migration safety runbook

Audit follow-up 2026-05-05 (M4). Several migrations shipped before this
runbook used patterns that were safe on tiny tables but become locking
or replication hazards as data grows. The patterns below are the ones
to use going forward; the "what NOT to do" sections are the ones we
know about today.

This document is **prescriptive**, not retroactive — past migrations
already ran successfully on small tables, and rewriting them now would
just churn the history. New PRs go through the patterns below.

---

## TL;DR — copy-paste templates

### Add an index

```python
def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_<table>_<col> "
            "ON <table> (<col>)"
        )

def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_<table>_<col>")
```

`CONCURRENTLY` mandatory; `IF NOT EXISTS` idempotent; `autocommit_block`
required (Postgres rejects `CREATE INDEX CONCURRENTLY` inside a tx).

### Drop an INVALID index (failed REINDEX leftovers)

```python
op.execute("DROP INDEX IF EXISTS <ghost_name>")  # NOT CONCURRENTLY
```

`DROP INDEX CONCURRENTLY` silently no-ops on `indisvalid=false`
indexes — this caused PR #46 to leave the ghost in place on the first
attempt. Use plain `DROP INDEX`. The `AccessExclusiveLock` is
metadata-only (the index is invalid so no rows reference it), held
for milliseconds.

### Add a NOT NULL column with a default

```python
def upgrade() -> None:
    # 1. Add nullable, no default. Instant — metadata only.
    op.add_column("users", sa.Column("country_code", sa.String(2), nullable=True))
    # 2. Backfill in batches OUTSIDE this migration if the table is large.
    #    For < 50k rows it's fine inline.
    op.execute("UPDATE users SET country_code = 'US' WHERE country_code IS NULL")
    # 3. Switch to NOT NULL via CHECK + VALIDATE (no full-table lock).
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT users_country_code_not_null "
        "CHECK (country_code IS NOT NULL) NOT VALID"
    )
    op.execute("ALTER TABLE users VALIDATE CONSTRAINT users_country_code_not_null")
    op.alter_column("users", "country_code", nullable=False)
    op.execute("ALTER TABLE users DROP CONSTRAINT users_country_code_not_null")
```

The `CHECK NOT VALID` + `VALIDATE` dance avoids the `ACCESS EXCLUSIVE`
lock that a direct `SET NOT NULL` would take to validate every row.

### Add a foreign key

```python
op.create_foreign_key(
    "fk_orders_market_id",
    source_table="orders",
    referent_table="markets",
    local_cols=["market_id"],
    remote_cols=["market_id"],
    # The default would validate every existing row at constraint creation
    # time — full-table scan + ACCESS EXCLUSIVE. Defer it.
    # (Use a separate migration for VALIDATE CONSTRAINT after backfill.)
)
op.execute(
    "ALTER TABLE orders DROP CONSTRAINT fk_orders_market_id, "
    "ADD CONSTRAINT fk_orders_market_id "
    "FOREIGN KEY (market_id) REFERENCES markets(market_id) NOT VALID"
)
# Then in a follow-up migration once the data is clean:
# op.execute("ALTER TABLE orders VALIDATE CONSTRAINT fk_orders_market_id")
```

### Drop a column

```python
op.drop_column("users", "old_field")
```

Cheap on Postgres (metadata-only — the storage stays until VACUUM).
Just make sure no live code or in-flight transactions reference the
column.

### Rename a column

**DON'T.** Renames break readers and writers running the old code at
the same moment as the migration. Use the expand–contract pattern:

1. Migration A — `ADD COLUMN new_name`, code writes both columns.
2. Backfill old → new in a script.
3. Code reads `new_name`, writes both.
4. Migration B — `DROP COLUMN old_name`.

---

## What NOT to do

### `UPDATE … WHERE … LIKE` without `LIMIT` or `WHERE id IN (…)`

Migration `014_news_source_id_fk.py` at line 28-35 ran an unbounded
`UPDATE news SET source_id = …` inside the migration transaction. On
the empty staging DB this was instant; on a populated `news` table at
~150 k rows it locks the whole table for the duration of the update.

**Better**: do the backfill in a separate one-off script that batches
by `WHERE id BETWEEN x AND y` with a 1000-row chunk and commits each
batch.

### `op.add_column(... vector(1536))` on a populated table

Migration `022_add_embedding_v2_columns.py` adds vector columns × 3
tables × 2 columns. On a populated `markets` table (192 k rows
today) this still completes — the column is created with NULL default
which is metadata-only — but on tables with rewriting defaults it
would lock for a full table scan.

**Better**: add the column with `nullable=True, server_default=None`,
then backfill in a script, then add NOT NULL via the CHECK + VALIDATE
pattern above if needed.

### `op.alter_column(... nullable=False)` on a populated table

Migration `026_user_profile_email_not_null_and_cleanup.py` line 79
runs `ALTER TABLE … SET NOT NULL` directly. `SET NOT NULL` validates
every existing row under `ACCESS EXCLUSIVE` — a full table scan that
blocks readers and writers.

**Better**: the CHECK + VALIDATE pattern above. The validation step
takes a `SHARE UPDATE EXCLUSIVE` lock which doesn't block reads or
writes.

### Mixing `CONCURRENTLY` with non-`CONCURRENTLY` in the same `autocommit_block`

Works (because each statement gets its own implicit transaction) but
is confusing. Either:
- All-CONCURRENTLY in one autocommit_block, OR
- Plain transactional migration with no autocommit_block.

PR #46 mixed both because the ghost-drop required non-concurrent
(invalid-index limitation). Acceptable when documented; avoid as a
default.

---

## Process

1. Migration writer reads this doc before writing the upgrade body.
2. Reviewer compares the proposed migration against the templates;
   any deviation must be justified in the PR description.
3. After merge, migration applies in the Docker entrypoint via
   `alembic upgrade head` BEFORE uvicorn boots (see
   `docker-compose.yml`'s `app` service `command`).
4. If a migration fails on prod, the entrypoint exits non-zero and
   the `app` container restarts in a loop — that's the visible
   failure signal. Don't wrap migration failures in try/except just
   to "keep booting."

---

## See also

- **Live audit 2026-05-05** — produced this doc and the index/cleanup PRs
  (#46, #53, #59).
- **Postgres docs**: https://www.postgresql.org/docs/16/sql-altertable.html
- **Pgcat / pgbouncer transaction-pooling caveat**: `CREATE INDEX
  CONCURRENTLY` cannot run through transaction-pooled connections.
  Our setup uses a session-pooled connection from Alembic so this is
  not currently an issue — but if we move Alembic to pgbouncer, the
  CONCURRENTLY pattern needs adjusting.
