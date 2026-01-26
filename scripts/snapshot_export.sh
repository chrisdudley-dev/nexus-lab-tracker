#!/usr/bin/env bash
set -euo pipefail

# Snapshot exporter for Nexus Lab Tracker (Model 1 scope):
# - Creates a point-in-time SQLite backup
# - Writes basic metadata and summaries
# - Produces a portable tar.gz artifact

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

: "${EXPORTS_DIR:=exports}"
if [[ "$EXPORTS_DIR" != /* ]]; then
  EXPORTS_DIR="$REPO_ROOT/$EXPORTS_DIR"
fi

# Respect DB_PATH if provided; otherwise use the project default via lims.db
DB="$(python3 - <<'PY'
import os
from lims.db import db_path
print(db_path())
PY
)"

if [[ ! -f "$DB" ]]; then
  echo "ERROR: DB not found at: $DB" >&2
  echo "HINT: Run ./scripts/lims.sh init (or set DB_PATH) before exporting a snapshot." >&2
  exit 2
fi

TS_UTC="$(date -u +%Y%m%d-%H%M%SZ)"
SNAP_DIR="$EXPORTS_DIR/snapshot-$TS_UTC"
mkdir -p "$SNAP_DIR"

# Metadata
DB_BYTES="$( (stat -c%s "$DB" 2>/dev/null) || (wc -c <"$DB") )"
{
  echo "snapshot_utc=$TS_UTC"
  echo "repo_root=$REPO_ROOT"
  echo "db_path=$DB"
  echo "db_bytes=$DB_BYTES"
  if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "git_head=$(git rev-parse HEAD)"
    echo "git_branch=$(git rev-parse --abbrev-ref HEAD)"
  fi
} > "$SNAP_DIR/meta.txt"

# Git state (optional)
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  {
    echo "== git status --porcelain =="
    git status --porcelain || true
    echo
    echo "== git diff --stat =="
    git diff --stat || true
  } > "$SNAP_DIR/git.txt"
fi

# DB backup + schema + quick counts
if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "ERROR: sqlite3 is required for snapshot_export.sh" >&2
  exit 2
fi

sqlite3 "$DB" ".backup '$SNAP_DIR/lims.sqlite3'"
sqlite3 "$SNAP_DIR/lims.sqlite3" ".schema" > "$SNAP_DIR/schema.sql"

sqlite3 "$SNAP_DIR/lims.sqlite3" <<'SQL' > "$SNAP_DIR/summary.txt"
.headers on
.mode column

SELECT 'samples'     AS table_name, COUNT(*) AS rows FROM samples;
SELECT 'containers'  AS table_name, COUNT(*) AS rows FROM containers;
SELECT 'audit_events' AS table_name, COUNT(*) AS rows FROM audit_events;

-- Optional: show most recent audit events (if present)
SELECT
  id,
  event_type,
  entity_type,
  entity_id,
  occurred_at
FROM audit_events
ORDER BY occurred_at DESC, id DESC
LIMIT 20;
SQL

# Include migrations and CLI scripts for forensic reproducibility
mkdir -p "$SNAP_DIR/migrations" "$SNAP_DIR/scripts"
cp -a migrations/. "$SNAP_DIR/migrations/"
cp -a scripts/lims.sh scripts/migrate.sh "$SNAP_DIR/scripts/"

# Tarball artifact for easy transfer
TARBALL="$EXPORTS_DIR/snapshot-$TS_UTC.tar.gz"
tar -czf "$TARBALL" -C "$EXPORTS_DIR" "snapshot-$TS_UTC"

echo "OK: wrote snapshot directory: $SNAP_DIR"
echo "OK: wrote artifact:          $TARBALL"
