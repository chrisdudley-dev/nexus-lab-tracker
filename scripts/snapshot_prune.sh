#!/usr/bin/env bash
set -euo pipefail
fail(){ echo "ERROR: $*" >&2; exit 2; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

dir="${EXPORTS_DIR:-}"
pins_file=""
keep=10
apply=0
verbose=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) [[ $# -ge 2 ]] || fail "--dir requires a value"; dir="$2"; shift 2 ;;
    --file) [[ $# -ge 2 ]] || fail "--file requires a value"; pins_file="$2"; shift 2 ;;
    --keep) [[ $# -ge 2 ]] || fail "--keep requires a value"; keep="$2"; shift 2 ;;
    --apply) apply=1; shift ;;
    --dry-run) apply=0; shift ;;
    -v|--verbose) verbose=1; shift ;;
    -h|--help)
      echo "Usage: ./scripts/lims.sh snapshot prune [--keep N] [--dir PATH] [--file PINS_FILE] [--apply] [--dry-run] [-v]"
      echo "  Default is dry-run (no deletion). Use --apply to actually delete."
      echo "  Always preserves pinned snapshots (pins file) plus newest --keep N."
      exit 0 ;;
    *) fail "unknown arg: $1" ;;
  esac
done

[[ "$keep" =~ ^[0-9]+$ ]] || fail "--keep must be a non-negative integer"

if [[ -z "$dir" ]]; then
  [[ -d "$REPO_ROOT/exports" ]] || fail "EXPORTS_DIR not set and ./exports not found (use --dir PATH)"
  dir="$REPO_ROOT/exports"
fi
[[ "$dir" == /* ]] || dir="$REPO_ROOT/$dir"
[[ -d "$dir" ]] || fail "exports dir not found: $dir"

if [[ -z "$pins_file" ]]; then
  pins_file="${SNAPSHOT_PINS_FILE:-$dir/.snapshot_pins}"
fi
[[ "$pins_file" == /* ]] || pins_file="$REPO_ROOT/$pins_file"

# Load pins into associative set
declare -A pinned=()
if [[ -f "$pins_file" ]]; then
  while IFS= read -r line; do
    line="${line%%#*}"
    line="$(echo "$line" | sed 's/[[:space:]]*$//')"
    [[ -n "$line" ]] || continue
    pinned["$line"]=1
  done < "$pins_file"
fi

mapfile -t files < <(
  find "$dir" -maxdepth 1 -type f \( -name 'snapshot-*.tar.gz' -o -name 'snapshot-*.tgz' \) -printf '%f\n' 2>/dev/null | sort -r
)

[[ ${#files[@]} -gt 0 ]] || { echo "OK: nothing to prune (no snapshots found in $dir)"; exit 0; }

declare -A keepers=()

# keep newest N
for ((i=0; i<${#files[@]} && i<keep; i++)); do
  keepers["${files[$i]}"]=1
done

# keep pinned always
for k in "${!pinned[@]}"; do
  keepers["$k"]=1
done

# deletion candidates
to_delete=()
for f in "${files[@]}"; do
  if [[ -z "${keepers[$f]:-}" ]]; then
    to_delete+=("$f")
  fi
done

if [[ ${#to_delete[@]} -eq 0 ]]; then
  echo "OK: nothing to prune (all snapshots are within keep set or pinned)"
  exit 0
fi

# Plan deletions (tarballs + matching dirs)
tar_del=0
dir_del=0

echo "== Snapshot Prune Plan =="
echo "dir: $dir"
echo "pins_file: $pins_file"
echo "keep newest: $keep"
echo "mode: $([[ $apply -eq 1 ]] && echo APPLY || echo DRY-RUN)"

for f in "${to_delete[@]}"; do
  [[ "$f" != *"/"* ]] || fail "refusing to delete suspicious name (contains '/'): $f"
  echo "DELETE tarball: $dir/$f"
  tar_del=$((tar_del+1))

  d="${f%.tar.gz}"
  d="${d%.tgz}"
  if [[ -d "$dir/$d" ]]; then
    echo "DELETE dir:     $dir/$d"
    dir_del=$((dir_del+1))
  else
    (( verbose )) && echo "KEEP dir:       (not found) $dir/$d"
  fi
done

if (( apply == 0 )); then
  echo "DRY-RUN: would delete $tar_del tarball(s), $dir_del dir(s)."
  exit 0
fi

# Apply deletions
for f in "${to_delete[@]}"; do
  rm -f -- "$dir/$f"
  d="${f%.tar.gz}"
  d="${d%.tgz}"
  [[ -d "$dir/$d" ]] && rm -rf -- "$dir/$d" || true
done

echo "OK: pruned $tar_del tarball(s), $dir_del dir(s)."
