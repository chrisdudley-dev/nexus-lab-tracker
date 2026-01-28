#!/usr/bin/env bash
set -euo pipefail

JSON_MODE="${SNAPSHOT_JSON:-0}"

# JSON mode: keep stdout strictly machine-readable (JSON only).
# Route all other output (including OK lines) to stderr.
if [[ "$JSON_MODE" == "1" ]]; then
  exec 3>&1
  exec 1>&2
fi

# Helper: returns 0 if table exists, 1 otherwise
sqlite_table_exists() {
  local db="$1" table="$2"
  sqlite3 "$db" "SELECT 1 FROM sqlite_master WHERE type='table' AND name='$table' LIMIT 1;" | grep -q '^1$'
}


# Snapshot exporter for Nexus Lab Tracker (Model 1 scope):
# - Creates a point-in-time SQLite backup
# - Writes basic metadata and summaries
# - Produces a portable tar.gz artifact

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

: "${EXPORTS_DIR:=${EXPORT_DIR:-exports}}"
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
BASE="$EXPORTS_DIR/snapshot-$TS_UTC"
SNAP_DIR="$BASE"
i=0
while [[ -e "$SNAP_DIR" ]]; do
  i=$((i+1))
  SNAP_DIR="${BASE}-$i"
done
mkdir -p "$SNAP_DIR"
: > "$SNAP_DIR/summary.txt"

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

# Optional: include sample export artifacts inside the snapshot bundle.
# Identifiers are space-delimited in SNAPSHOT_INCLUDE_SAMPLES (set by scripts/lims.sh).
if [[ -n "${SNAPSHOT_INCLUDE_SAMPLES:-}" ]]; then
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  mkdir -p "$SNAP_DIR/exports/samples"
  for ident in $SNAPSHOT_INCLUDE_SAMPLES; do
    safe="$(printf %s "$ident" | tr -cs 'A-Za-z0-9._-' '_' )"
    safe="${safe%_}"
    out="$SNAP_DIR/exports/samples/sample-$safe.json"
    tmp_out="$(mktemp "${out}.tmp.XXXXXX")"
    if DB_PATH="$SNAP_DIR/lims.sqlite3" "$script_dir/lims.sh" sample export "$ident" --format json >"$tmp_out"; then
      mv -f "$tmp_out" "$out"
    else
      rm -f "$tmp_out"
      echo "ERROR: failed to export sample '$ident' into snapshot" >&2
      exit 2
    fi
  done
fi
sqlite3 "$SNAP_DIR/lims.sqlite3" ".schema" > "$SNAP_DIR/schema.sql"

if sqlite_table_exists "$SNAP_DIR/lims.sqlite3" audit_events; then
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
else
  # Model 1 scope: audit_events may not exist yet; skip quietly.
  :
fi

# Include migrations and CLI scripts for forensic reproducibility
mkdir -p "$SNAP_DIR/migrations" "$SNAP_DIR/scripts"
cp -a migrations/. "$SNAP_DIR/migrations/"
cp -a scripts/lims.sh scripts/migrate.sh "$SNAP_DIR/scripts/"

# Tarball artifact for easy transfer
SNAP_BASENAME="$(basename "$SNAP_DIR")"
TARBALL="$EXPORTS_DIR/${SNAP_BASENAME}.tar.gz"
tar -czf "$TARBALL" -C "$EXPORTS_DIR" "$SNAP_BASENAME"

if [[ "$JSON_MODE" == "1" ]]; then
  echo "OK: wrote snapshot directory: $SNAP_DIR" >&2
  echo "OK: wrote artifact:          $TARBALL" >&2
else
  echo "OK: wrote snapshot directory: $SNAP_DIR"
  echo "OK: wrote artifact:          $TARBALL"
fi

# ---- Snapshot manifest (self-describing artifact + integrity hashes) ----
manifest="$SNAP_DIR/manifest.json"

# Best-effort git commit for provenance (empty if not available)
# Avoid relying on script_dir (may be unset); compute repo root from this script's location.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
git_commit=""
if command -v git >/dev/null 2>&1; then
  if git -C "$repo_root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git_commit="$(git -C "$repo_root" rev-parse HEAD 2>/dev/null || true)"
  fi
fi

created_at_utc="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
db_path="$SNAP_DIR/lims.sqlite3"
db_sha256="$(sha256sum "$db_path" | awk '{print $1}')"

# Best-effort tarball location (sibling of snapshot dir)
tar_path="$TARBALL"
tar_sha256=""
if [[ -f "$tar_path" ]]; then
  tar_sha256="$(sha256sum "$tar_path" | awk '{print $1}')"
else
  tar_path=""
fi

export created_at_utc git_commit db_sha256 tar_path tar_sha256 SNAPSHOT_INCLUDE_SAMPLES

python3 - "$manifest" <<'PYMAN'
import hashlib, json, os, sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
snap_dir = manifest_path.parent

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

doc = {
    "schema": "nexus_snapshot_manifest",
    "schema_version": 2,
    "created_at_utc": os.environ.get("created_at_utc", ""),
    "git_commit": os.environ.get("git_commit", ""),
    "snapshot_dir": ".",
    "db": {"path": "lims.sqlite3", "sha256": os.environ.get("db_sha256", "")},
    "tarball": None,
    "included_exports": {"samples": []},
}

tar_path = os.environ.get("tar_path", "")
tar_sha  = os.environ.get("tar_sha256", "")
if tar_path and tar_sha:
    doc["tarball"] = {"path": str(Path("..") / Path(tar_path).name), "sha256": tar_sha}

samples_dir = snap_dir / "exports" / "samples"
for ident in [x for x in os.environ.get("SNAPSHOT_INCLUDE_SAMPLES", "").split() if x.strip()]:
    safe = ident.strip().replace("/", "_")
    fp = samples_dir / f"sample-{safe}.json"
    rel = fp.relative_to(snap_dir)
    entry = {"external_id": ident, "path": str(rel)}
    if fp.exists():
        entry["sha256"] = sha256_file(fp)
    else:
        entry["sha256"] = None
        entry["missing"] = True
    doc["included_exports"]["samples"].append(entry)

manifest_path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PYMAN

# ---- JSON result (stdout only) ----
if [[ "$JSON_MODE" == "1" ]]; then
  export SNAP_DIR TARBALL EXPORTS_DIR created_at_utc SNAPSHOT_INCLUDE_SAMPLES
  python3 - <<'PYJSON' >&3
import json, os
doc = {
  "schema": "nexus_snapshot_export_result",
  "schema_version": 1,
  "ok": True,
  "snapshot_dir": os.environ.get("SNAP_DIR",""),
  "tarball": os.environ.get("TARBALL",""),
  "exports_dir": os.environ.get("EXPORTS_DIR",""),
  "included_samples": [x for x in os.environ.get("SNAPSHOT_INCLUDE_SAMPLES","").split() if x.strip()],
  "created_at_utc": os.environ.get("created_at_utc",""),
}
print(json.dumps(doc, sort_keys=True, separators=(",",":")) )
PYJSON
  exec 3>&-
fi
