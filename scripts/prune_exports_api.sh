#!/usr/bin/env bash
set -Eeuo pipefail

KEEP="${1:-20}"
DRY_RUN="${DRY_RUN:-0}"

if [[ "$KEEP" == "--dry-run" ]]; then
  DRY_RUN=1
  KEEP="${2:-20}"
fi

if ! [[ "$KEEP" =~ ^[0-9]+$ ]]; then
  echo "Usage: $0 [KEEP_COUNT] [--dry-run]" >&2
  echo "  or:  DRY_RUN=1 $0 [KEEP_COUNT]" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
ROOT="$REPO_ROOT/exports/api"

mkdir -p "$ROOT"

# List tarballs newest-first (mtime); keep newest $KEEP, delete the rest.
mapfile -t TARS < <(find "$ROOT" -maxdepth 1 -type f -name '*.tar.gz' -printf '%T@ %p\n' \
  | sort -nr | awk '{print $2}')

total="${#TARS[@]}"
if (( total <= KEEP )); then
  echo "OK: exports/api has $total tarballs; keep=$KEEP; nothing to prune."
  exit 0
fi

echo "Pruning exports/api: total=$total keep=$KEEP dry_run=$DRY_RUN"
to_delete=("${TARS[@]:KEEP}")

for f in "${to_delete[@]}"; do
  [[ -n "$f" ]] || continue

  # Safety: must stay under ROOT
  fp="$(cd "$(dirname "$f")" && pwd -P)/$(basename "$f")"
  if [[ "$fp" != "$ROOT/"* ]]; then
    echo "REFUSING: outside exports/api: $fp" >&2
    exit 1
  fi

  base="$(basename "$fp" .tar.gz)"
  dir="$ROOT/$base"

  if (( DRY_RUN == 1 )); then
    echo "DRY: rm -f $fp"
    [[ -d "$dir" ]] && echo "DRY: rm -rf $dir"
    continue
  fi

  rm -f -- "$fp"
  [[ -d "$dir" ]] && rm -rf -- "$dir"
done

echo "OK: pruned $(( total - KEEP )) tarballs (kept newest $KEEP)."
