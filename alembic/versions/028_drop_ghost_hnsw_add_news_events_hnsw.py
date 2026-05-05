"""Drop ghost HNSW index on markets + add HNSW on news_clean / events embeddings.

Revision ID: 028
Revises: 027
Create Date: 2026-05-05

Two related fixes audit-2026-05-05 surfaced:

1. **Drop `idx_markets_embedding_hnsw_ccnew`** — leftover from a failed
   `REINDEX CONCURRENTLY` ages ago. Lives in `pg_index` with
   `indisvalid=false, indisready=false`, so the planner ignores it, but
   it occupies ~526 MB of disk *and* gets touched on every market write
   (write amplification). The `CONCURRENTLY` form needs autocommit and
   no in-transaction wrapper, hence the `autocommit_block()`.

2. **Add HNSW on `news_clean.embedding(_v2)` and `events.embedding(_v2)`** —
   migration 022 added the `embedding_v2` columns but no companion HNSW
   migration was ever shipped for these two tables. Today the data is
   small (news_clean ~400 rows, events ~6.5k) so a sequential scan is
   tolerable, but `app/retrieval/vector_retriever.py` queries them with
   `ORDER BY embedding <=> :q` on every retrieval — the moment ingestion
   ramps to a few thousand articles per day this becomes O(n) on every
   request and latency blows up. Shipping the indexes now means the
   data-volume curve doesn't get to bite us.

Both operations use `IF EXISTS / IF NOT EXISTS` so the migration is
idempotent — running it twice is safe, and re-running on a fresh DB
that doesn't have the ghost index yet is also safe.

`m=16, ef_construction=64` are the pgvector defaults and what
migrations 003 and 023 used on `markets`. Keep the parameter set
consistent across all four embedding columns so query latency profiles
stay comparable.
"""

from __future__ import annotations

from alembic import op


revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        # 1. Drop the ghost first — frees ~150-526 MB (size varies with how
        # far the failed REINDEX got) and stops the write amplification
        # before we add four more HNSW indexes that every market write
        # will need to maintain.
        #
        # Note: we use a *plain* DROP INDEX, not DROP INDEX CONCURRENTLY.
        # The first cut of this migration tried CONCURRENTLY but Postgres
        # silently no-ops it for `indisvalid = false` indexes — they have
        # to be dropped non-concurrently. The brief AccessExclusiveLock on
        # `markets` is fine because (a) no query plan ever references an
        # invalid index so cancelling readers is unnecessary, and (b) the
        # drop itself is metadata-only once the index is invalid (no row
        # cleanup), so the lock is held for milliseconds. If a long-running
        # REINDEX is concurrently rebuilding the same index, you'll need
        # to cancel its backend before this DROP can grab the lock — see
        # the runbook for the 2026-05-05 incident where three zombie
        # REINDEX backends had to be `pg_cancel_backend`'d first.
        op.execute(
            "DROP INDEX IF EXISTS idx_markets_embedding_hnsw_ccnew"
        )

        # 2. Add HNSW on the four missing embedding columns. `IF NOT EXISTS`
        # means re-running on a partially-applied state is safe.
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_news_clean_embedding_hnsw "
            "ON news_clean USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_news_clean_embedding_v2_hnsw "
            "ON news_clean USING hnsw (embedding_v2 vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_events_embedding_hnsw "
            "ON events USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_events_embedding_v2_hnsw "
            "ON events USING hnsw (embedding_v2 vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        # Only drop the four indexes we added — we do *not* re-create the
        # ghost on downgrade. Recreating an `indisvalid=false` index is
        # impossible from SQL anyway; the ghost was a consequence of a
        # failed REINDEX, not an artifact a migration ever wanted.
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_events_embedding_v2_hnsw")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_events_embedding_hnsw")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_news_clean_embedding_v2_hnsw")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_news_clean_embedding_hnsw")
