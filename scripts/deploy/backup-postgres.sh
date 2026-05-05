#!/usr/bin/env bash
# Daily Postgres backup — pg_dump from the docker-compose `db` service
# to /var/backups/foresight, with 14-day rotation.
#
# Install:
#   $ cp scripts/deploy/backup-postgres.sh /usr/local/bin/foresight-backup
#   $ chmod +x /usr/local/bin/foresight-backup
#   $ echo "0 3 * * * /usr/local/bin/foresight-backup" | crontab -
#
# Smoke test:
#   $ /usr/local/bin/foresight-backup
#   $ ls -lh /var/backups/foresight/
#
# Restore:
#   $ gunzip < /var/backups/foresight/backup-YYYYMMDD.sql.gz \
#       | docker exec -i foresight-db psql -U postgres signal

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/foresight}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
CONTAINER="${CONTAINER:-foresight-db}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-signal}"

mkdir -p "$BACKUP_DIR"

STAMP="$(date -u +%Y%m%d-%H%M%S)"
TARGET="$BACKUP_DIR/backup-$STAMP.sql.gz"

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Starting pg_dump → $TARGET"

# --no-owner / --no-privileges keeps the dump portable across DB users.
# --format=plain + gzip is intentionally NOT --format=custom: plain dumps
# are greppable, easier to inspect, and round-trip cleanly through
# `psql` even on a different Postgres minor version. Custom format is
# slightly smaller on disk but the operational ease wins here.
docker exec "$CONTAINER" \
    pg_dump \
        --username="$DB_USER" \
        --no-owner \
        --no-privileges \
        --format=plain \
        "$DB_NAME" \
    | gzip -9 > "$TARGET"

SIZE="$(du -h "$TARGET" | cut -f1)"
echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Done. Size: $SIZE"

# Rotation — keep the last N days. Don't bother if RETENTION_DAYS=0.
if [ "$RETENTION_DAYS" -gt 0 ]; then
    DELETED=$(find "$BACKUP_DIR" -name "backup-*.sql.gz" -mtime "+$RETENTION_DAYS" -print -delete | wc -l)
    if [ "$DELETED" -gt 0 ]; then
        echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Rotated out $DELETED backup(s) older than $RETENTION_DAYS days."
    fi
fi

# Sanity — at least one valid backup must exist after we run.
LATEST=$(find "$BACKUP_DIR" -name "backup-*.sql.gz" -size +0c | sort | tail -1)
if [ -z "$LATEST" ]; then
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] ERROR: backup directory is empty or all dumps are zero-byte." >&2
    exit 1
fi

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Latest valid backup: $LATEST"
