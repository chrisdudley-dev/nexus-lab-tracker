#!/usr/bin/env bash
set -euo pipefail
fail(){ echo "ERROR: $*" >&2; exit 2; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

dir="${EXPORTS_DIR:-}"
pins_file=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) [[ $# -ge 2 ]] || fail "--dir requires a value"; dir="$2"; shift 2 ;;
    --file) [[ $# -ge 2 ]] || fail "--file requires a value"; pins_file="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: ./scripts/lims.sh snapshot pins [--dir PATH] [--file PINS_FILE]"
      echo "  Prints pinned snapshot basenames (one per line)."
      exit 0 ;;
    *) fail "unknown arg: $1" ;;
  esac
done

if [[ -z "$dir" ]]; then
  [[ -d "$REPO_ROOT/exports" ]] || fail "EXPORTS_DIR not set and ./exports not found (use --dir PATH)"
  dir="$REPO_ROOT/exports"
fi
[[ "$dir" == /* ]] || dir="$REPO_ROOT/$dir"

if [[ -z "$pins_file" ]]; then
  pins_file="${SNAPSHOT_PINS_FILE:-$dir/.snapshot_pins}"
fi
[[ "$pins_file" == /* ]] || pins_file="$REPO_ROOT/$pins_file"

[[ -f "$pins_file" ]] || exit 0
grep -E '^[^#[:space:]].*$' "$pins_file" | sed 's/[[:space:]]*$//' | awk 'NF' || true
