#!/usr/bin/env bash
set -euo pipefail

# JERBOA_SNAPSHOT_VERIFY_JSON_V1
# Contract: in --json mode, human logs go to stderr; exactly one JSON object goes to stdout.
__SV_JSON=0
__SV_EMITTED=0
__SV_KEEP=()
for __sv_a in "$@"; do
  if [[ "$__sv_a" == "--json" ]]; then
    __SV_JSON=1
  else
    __SV_KEEP+=("$__sv_a")
  fi
done
set -- "${__SV_KEEP[@]}"
unset __SV_KEEP __sv_a

# Also allow env toggle
if [[ "${SNAPSHOT_JSON:-0}" == "1" ]]; then
  __SV_JSON=1
fi

# Reserve fd3 as original stdout; move stdout -> stderr in json mode
if [[ "$__SV_JSON" == "1" ]]; then
  exec 3>&1
  exec 1>&2
fi

__sv_emit_json() {
  [[ "$__SV_JSON" == "1" ]] || return 0
  local ok="$1" rc="$2" msg="${3:-}"
  local art="${SNAPSHOT_ARTIFACT:-${ART:-}}"
  local db="${SRC_DB:-}"
  SNAPSHOT_VERIFY_OK="$ok" \
  SNAPSHOT_VERIFY_RC="$rc" \
  SNAPSHOT_VERIFY_MSG="$msg" \
  SNAPSHOT_VERIFY_ARTIFACT="$art" \
  SNAPSHOT_VERIFY_DB="$db" \
  python3 -c 'import os,json,datetime
ok=os.environ.get("SNAPSHOT_VERIFY_OK","false").lower() in ("1","true","yes")
rc=int(os.environ.get("SNAPSHOT_VERIFY_RC","2"))
msg=os.environ.get("SNAPSHOT_VERIFY_MSG") or None
art=os.environ.get("SNAPSHOT_VERIFY_ARTIFACT") or None
db=os.environ.get("SNAPSHOT_VERIFY_DB") or None
doc={
 "schema":"nexus_snapshot_verify_result",
 "schema_version":1,
 "ok":ok,
 "rc":rc,
 "message":msg,
 "artifact":art,
 "resolved_snapshot_db":db,
 "ts_utc":datetime.datetime.utcnow().replace(microsecond=0).isoformat()+"Z",
}
print(json.dumps(doc, sort_keys=True))' >&3
}

# --json flag shim (sets SNAPSHOT_JSON=1)
# Accept --json as an alias for SNAPSHOT_JSON=1 (and remove it from args)
__json_req=0
__keep=()
for __a in "$@"; do
  if [[ "$__a" == "--json" ]]; then
    __json_req=1
  else
    __keep+=("$__a")
  fi
done
set -- "${__keep[@]}"
unset __keep __a
if [[ "$__json_req" == "1" ]]; then
  export SNAPSHOT_JSON=1
fi
unset __json_req

# JSON MODE (snapshot_verify)
# If SNAPSHOT_JSON=1, redirect human logs to stderr and emit exactly one JSON object to stdout.
JSON_MODE="${SNAPSHOT_JSON:-0}"
if [[ "${JSON_MODE}" == "1" ]]; then
  exec 3>&1
  exec 1>&2
fi

emit_json() {
  [[ "${JSON_MODE}" == "1" ]] || return 0
  SNAPSHOT_VERIFY_OK="$1" \
  SNAPSHOT_VERIFY_RC="$2" \
  SNAPSHOT_VERIFY_MSG="${3:-}" \
  SNAPSHOT_VERIFY_ARTIFACT="${SNAPSHOT_ARTIFACT:-${ART:-}}" \
  SNAPSHOT_VERIFY_DB="${SRC_DB:-}" \
  python3 -c 'import os,json,datetime
ok=os.environ.get("SNAPSHOT_VERIFY_OK","false").lower() in ("1","true","yes")
rc=int(os.environ.get("SNAPSHOT_VERIFY_RC","2"))
msg=os.environ.get("SNAPSHOT_VERIFY_MSG") or None
art=os.environ.get("SNAPSHOT_VERIFY_ARTIFACT") or None
db=os.environ.get("SNAPSHOT_VERIFY_DB") or None
doc={
 "schema":"nexus_snapshot_verify_result",
 "schema_version":1,
 "ok":ok,
 "rc":rc,
 "message":msg,
 "artifact":art,
 "resolved_snapshot_db":db,
 "ts_utc":datetime.datetime.utcnow().replace(microsecond=0).isoformat()+"Z",
}
print(json.dumps(doc, sort_keys=True))' >&3
}


# JSON output mode:
# - When enabled, send human logs to stderr and emit a single JSON object to stdout.
JSON_MODE="${SNAPSHOT_JSON:-0}"
ARGS=()
for a in "$@"; do
  if [[ "$a" == "--json" ]]; then
    JSON_MODE=1
  else
    ARGS+=("$a")
  fi
done
set -- "${ARGS[@]}"

emit_json() {
  [[ "$JSON_MODE" == "1" ]] || return 0
  python3 - "$1" "$2" "${3:-}" "${SNAPSHOT_ARTIFACT:-${ART:-}}" <<'PYJ' >&3
import json, sys, datetime
ok_s, rc_s, msg, art = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
doc = {
  "schema": "nexus_snapshot_verify_result",
  "schema_version": 1,
  "ok": (ok_s.lower() in ("1","true","yes")),
  "rc": int(rc_s),
  "artifact": (art if art else None),
  "message": (msg if msg else None),
  "ts_utc": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
}
print(json.dumps(doc, sort_keys=True))
PYJ
}

if [[ "$JSON_MODE" == "1" ]]; then
  # Redirect normal stdout to stderr; keep fd 3 for JSON stdout.
  exec 3>&1
  exec 1>&2
  trap 'rc=$?; if [[ $rc -eq 0 ]]; then emit_json true 0 "OK"; fi' EXIT
fi

# snapshot verify: validate a snapshot artifact WITHOUT restoring it as live DB
# rc=0 OK, rc=2 verification failure

  emit_json false 2 "$*"
fail() {
  echo "ERROR: $*" >&2
  if [[ "${__SV_JSON:-0}" == "1" ]]; then
    __SV_EMITTED=1
    __sv_emit_json false 2 "$*"
  fi
  exit 2
}

have() { command -v "$1" >/dev/null 2>&1; }

safe_extract_tgz() {
  local art="$1" dest="$2"
  local list count
  list="$(tar -tzf "$art")" || fail "tar -tzf failed: $art"
  count="$(printf "%s\n" "$list" | sed "/^$/d" | wc -l | tr -d " ")"
  if [[ "${count:-0}" -gt 2000 ]]; then
    fail "tarball too large ($count entries): $art"
  fi
  if printf "%s\n" "$list" | grep -Eq "(^/|(^|/)\.\.(/|$))"; then
    printf "%s\n" "$list" | grep -E "(^/|(^|/)\.\.(/|$))" | sed "s/^/UNSAFE: /" >&2
    fail "unsafe paths in tarball (path traversal) - refusing to extract"
  fi
  
  # Extra hardening: reject symlinks/hardlinks/devices/pipes/sockets, and cap total unpacked bytes.
  local tlist total max_total
  max_total="${NEXUS_SNAPSHOT_TAR_MAX_TOTAL_BYTES:-200000000}"   # 200MB default

  tlist="$(tar -tvzf "$art")" || { echo "ERROR: tar -tvzf failed: $art" >&2; exit 2; }

  # File type is first char of perms (e.g. -, d, l, b, c, p, s, h). Reject l/h/b/c/p/s.
  if printf "%s\n" "$tlist" | awk '{print $1}' | grep -Eq '^[lhbcps]'; then
    printf "%s\n" "$tlist" | awk '$1 ~ /^[lhbcps]/ {print "UNSAFE-TYPE: " $0}' >&2
    echo "ERROR: tarball contains symlinks/hardlinks/devices/pipes/sockets - refusing to extract" >&2
    exit 2
  fi

  # Zip-bomb guard: sum sizes in a tar listing (GNU tar vs bsdtar formats).
  total="$(printf "%s\n" "$tlist" | awk '
    BEGIN{sum=0}
    {
      # GNU tar: perms owner/group size YYYY-MM-DD HH:MM name
      if ($4 ~ /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/) {
        if ($3 ~ /^[0-9]+$/) sum += $3
      }
      # bsdtar: perms links user group size Mon DD HH:MM name
      else if ($6 ~ /^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$/) {
        if ($5 ~ /^[0-9]+$/) sum += $5
      }
    }
    END{print sum+0}
  ')"
  if [[ "${total:-0}" -gt "${max_total:-0}" ]]; then
    echo "ERROR: tarball uncompressed total too large (${total} bytes > ${max_total}) - refusing to extract" >&2
    exit 2
  fi

  tar -xzf "$art" -C "$dest" --no-same-owner --no-same-permissions
}


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
      safe_extract_tgz "$ART" "$tmpdir"
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
if [[ "${__SV_JSON:-0}" == "1" ]]; then __SV_EMITTED=1; __sv_emit_json true 0 "OK"; fi
