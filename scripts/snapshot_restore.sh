#!/usr/bin/env bash
set -euo pipefail

# Snapshot restorer for Nexus Lab Tracker (Model 2 scope):
# - Restores a snapshot SQLite DB (from snapshot dir or tar.gz) into DB_PATH
# - Enforces operator-safe overwrite rules (--force)
# - Optionally backs up existing DB (--backup)
# - Runs migrations after restore to upgrade old snapshots forward
# - Prints quick verification counts

# Helper: returns 0 if table exists, 1 otherwise
sqlite_table_exists() {
  local db="$1" table="$2"
  sqlite3 "$db" "SELECT 1 FROM sqlite_master WHERE type='table' AND name='$table' LIMIT 1;" | grep -q '^1$'
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export REPO_ROOT

ART="${SNAPSHOT_ARTIFACT:-}"
FORCE="${SNAPSHOT_FORCE:-0}"
BACKUP="${SNAPSHOT_BACKUP:-0}"

if [[ -z "$ART" ]]; then
  echo "ERROR: missing snapshot artifact path (SNAPSHOT_ARTIFACT)" >&2
  exit 2
fi

# Normalize artifact path
if [[ "$ART" != /* ]]; then
  ART="$REPO_ROOT/$ART"
fi

if [[ ! -e "$ART" ]]; then
  echo "ERROR: snapshot artifact not found: $ART" >&2
  exit 2
fi

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "ERROR: sqlite3 is required for snapshot_restore.sh" >&2
  exit 2
fi

# Resolve DB_PATH the same way the app does, but print an absolute path.
DB="$(python3 - <<'PY'
from lims.db import db_path
print(db_path().resolve())
PY
)"
DB_DIR="$(dirname "$DB")"
mkdir -p "$DB_DIR"

# Overwrite safety
TS_UTC="$(date -u +%Y%m%d-%H%M%SZ)"
if [[ -f "$DB" ]]; then
  if [[ "$FORCE" != "1" ]]; then
    echo "ERROR: target DB already exists: $DB" >&2
    echo "HINT: re-run with --force to overwrite" >&2
    echo "      optionally add --backup to keep a copy" >&2
    exit 2
  fi
  if [[ "$BACKUP" == "1" ]]; then
    cp -a "$DB" "${DB}.bak-${TS_UTC}"
    echo "OK: backed up existing DB to: ${DB}.bak-${TS_UTC}"
  fi
fi

# Determine source lims.sqlite3 from artifact
tmpdir=""
cleanup() {
  if [[ -n "${tmpdir:-}" && -d "$tmpdir" ]]; then
    rm -rf "$tmpdir"
  fi
}
trap cleanup EXIT

SRC_DB=""

if [[ -d "$ART" ]]; then
  # Common forms:
  # - snapshot-*/ (contains lims.sqlite3)
  # - direct directory containing lims.sqlite3
  if [[ -f "$ART/lims.sqlite3" ]]; then
    SRC_DB="$ART/lims.sqlite3"
  else
    # Look one level deep for a snapshot dir
    matches=( "$ART"/snapshot-*/lims.sqlite3 )
    if [[ ${#matches[@]} -ge 1 && -f "${matches[0]}" ]]; then
      # If multiple, prefer the first in lexicographic order (operator must pass exact path for ambiguous cases)
      SRC_DB="${matches[0]}"
    fi
  fi
elif [[ -f "$ART" ]]; then
  case "$ART" in
    *.tar.gz|*.tgz)
      tmpdir="$(mktemp -d)"
      tar -xzf "$ART" -C "$tmpdir"
      mapfile -t found < <(find "$tmpdir" -type f -name 'lims.sqlite3' | sort)
      if [[ ${#found[@]} -ne 1 ]]; then
        echo "ERROR: expected exactly 1 lims.sqlite3 in tarball, found ${#found[@]}" >&2
        if [[ ${#found[@]} -gt 0 ]]; then
          printf 'FOUND: %s\n' "${found[@]}" >&2
        fi
        exit 2
      fi
      SRC_DB="${found[0]}"
      ;;
    *.sqlite3)
      SRC_DB="$ART"
      ;;
    *)
      # allow a file named lims.sqlite3 without extension
      if [[ "$(basename "$ART")" == "lims.sqlite3" ]]; then
        SRC_DB="$ART"
      fi
      ;;
  esac
fi

if [[ -z "$SRC_DB" || ! -f "$SRC_DB" ]]; then
  echo "ERROR: could not locate lims.sqlite3 inside artifact: $ART" >&2
  echo "HINT: pass either:" >&2
  echo "  - a snapshot directory that contains lims.sqlite3" >&2
  echo "  - a snapshot-*.tar.gz created by snapshot export" >&2
  exit 2
fi

# Restore
cp -a "$SRC_DB" "$DB"
chmod 600 "$DB" || true
echo "OK: restored DB to: $DB"

# Ensure subsequent tools use the same DB
export DB_PATH="$DB"

echo "-> applying migrations (post-restore)"
./scripts/migrate.sh up

echo "-> migration status"
./scripts/migrate.sh status

echo "-> quick counts"
samples="$(sqlite3 "$DB" "SELECT COUNT(1) FROM samples;" 2>/dev/null || echo "?")"
containers="$(sqlite3 "$DB" "SELECT COUNT(1) FROM containers;" 2>/dev/null || echo "?")"
sample_events="?"
if sqlite_table_exists "$DB" sample_events; then
  sample_events="$(sqlite3 "$DB" "SELECT COUNT(1) FROM sample_events;" 2>/dev/null || echo "?")"
fi

audit_events="(absent)"
if sqlite_table_exists "$DB" audit_events; then
  audit_events="$(sqlite3 "$DB" "SELECT COUNT(1) FROM audit_events;" 2>/dev/null || echo "?")"
fi

echo "samples=$samples"
echo "containers=$containers"
echo "sample_events=$sample_events"
echo "audit_events=$audit_events"

echo "OK: snapshot restore complete."
