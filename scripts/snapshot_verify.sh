#!/usr/bin/env bash
set -euo pipefail

# snapshot verify: validate a snapshot artifact WITHOUT restoring it as live DB
# rc=0 OK, rc=2 verification failure

fail() { echo "ERROR: $*" >&2; exit 2; }
have() { command -v "$1" >/dev/null 2>&1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ART="${SNAPSHOT_ARTIFACT:-}"
DO_MIGRATE="${SNAPSHOT_DO_MIGRATE:-1}"

[[ -n "$ART" ]] || fail "missing snapshot artifact path"
[[ "$ART" == /* ]] || ART="$REPO_ROOT/$ART"
[[ -e "$ART" ]] || fail "snapshot artifact not found: $ART"

have sqlite3 || fail "sqlite3 is required"
have tar || true

tmpdir="$(mktemp -d)"
cleanup() { rm -rf "$tmpdir"; }
trap cleanup EXIT

SRC_DB=""

if [[ -d "$ART" ]]; then
  if [[ -f "$ART/lims.sqlite3" ]]; then
    SRC_DB="$ART/lims.sqlite3"
  else
    mapfile -t found < <(find "$ART" -maxdepth 2 -type f -name 'lims.sqlite3' | sort)
    if [[ ${#found[@]} -eq 1 ]]; then
      SRC_DB="${found[0]}"
    elif [[ ${#found[@]} -gt 1 ]]; then
      fail "ambiguous artifact: multiple lims.sqlite3 files found (pass exact snapshot dir)"
    fi
  fi
else
  case "$ART" in
    *.tar.gz|*.tgz)
      have tar || fail "tar is required to verify tar.gz snapshots"
      tar -xzf "$ART" -C "$tmpdir"
      mapfile -t found < <(find "$tmpdir" -type f -name 'lims.sqlite3' | sort)
      [[ ${#found[@]} -eq 1 ]] || { printf 'FOUND: %s\n' "${found[@]:-}" >&2; fail "expected exactly 1 lims.sqlite3 in tarball"; }
      SRC_DB="${found[0]}"
      ;;
    *.sqlite3)
      SRC_DB="$ART"
      ;;
    *)
      [[ "$(basename "$ART")" == "lims.sqlite3" ]] && SRC_DB="$ART" || true
      ;;
  esac
fi

[[ -n "$SRC_DB" && -f "$SRC_DB" ]] || fail "could not locate lims.sqlite3 inside artifact: $ART"

WORK_DB="$tmpdir/verify.sqlite3"
cp -a "$SRC_DB" "$WORK_DB"
chmod 600 "$WORK_DB" || true

echo "OK: located snapshot db: $SRC_DB"
echo "OK: copied to temp db:    $WORK_DB"

# 1) integrity_check
integrity_out="$(sqlite3 "$WORK_DB" "PRAGMA integrity_check;" 2>&1)" || { echo "$integrity_out" >&2; fail "sqlite integrity_check failed"; }
if [[ "$(echo "$integrity_out" | tr -d '\r' | tail -n 1)" != "ok" ]]; then
  echo "$integrity_out" >&2
  fail "sqlite integrity_check did not return ok"
fi
echo "OK: integrity_check = ok"

# 2) foreign_key_check
fk_out="$(sqlite3 "$WORK_DB" "PRAGMA foreign_keys=ON; PRAGMA foreign_key_check;" 2>&1)" || { echo "$fk_out" >&2; fail "foreign_key_check failed"; }
if [[ -n "$(echo "$fk_out" | tr -d '\r' | tr -d '[:space:]')" ]]; then
  echo "$fk_out" >&2
  fail "foreign_key_check reported violations"
fi
echo "OK: foreign_key_check = clean"

# 3) migrate forward in temp (default)
export DB_PATH="$WORK_DB"

if [[ "$DO_MIGRATE" == "1" ]]; then
  echo "-> applying migrations (verify-temp)"
  ./scripts/migrate.sh up

  echo "-> migration status (verify-temp)"
  status_out="$(./scripts/migrate.sh status || true)"
  echo "$status_out"
  python3 -c 'import json,sys
raw=sys.argv[1]
s=raw.find("{"); e=raw.rfind("}")
if s==-1 or e==-1 or e<s:
  print("ERROR: migrate status did not contain a JSON object", file=sys.stderr); sys.exit(2)
obj=json.loads(raw[s:e+1])
pending=obj.get("pending", None)
if pending != []:
  print(f"ERROR: migrations pending after verify-temp migrate: {pending}", file=sys.stderr); sys.exit(2)
print("OK: migrations at head (pending=[])")
' "$status_out"
fi

# 4) invariants via existing operator tooling (against temp DB_PATH)
echo "-> container audit (verify-temp)"
./scripts/lims.sh container audit >/dev/null
echo "OK: container audit = clean"

# 5) quick counts
samples="$(sqlite3 "$WORK_DB" "SELECT COUNT(1) FROM samples;" 2>/dev/null || echo "?")"
containers="$(sqlite3 "$WORK_DB" "SELECT COUNT(1) FROM containers;" 2>/dev/null || echo "?")"
sample_events="(absent)"
if sqlite3 "$WORK_DB" "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sample_events' LIMIT 1;" | grep -q '^1$'; then
  sample_events="$(sqlite3 "$WORK_DB" "SELECT COUNT(1) FROM sample_events;" 2>/dev/null || echo "?")"
fi

echo "samples=$samples"
echo "containers=$containers"
echo "sample_events=$sample_events"
echo "OK: snapshot verify complete."
