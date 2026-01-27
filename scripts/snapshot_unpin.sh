#!/usr/bin/env bash
set -euo pipefail
fail(){ echo "ERROR: $*" >&2; exit 2; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

dir="${EXPORTS_DIR:-}"
pins_file=""
artifact=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) [[ $# -ge 2 ]] || fail "--dir requires a value"; dir="$2"; shift 2 ;;
    --file) [[ $# -ge 2 ]] || fail "--file requires a value"; pins_file="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: ./scripts/lims.sh snapshot unpin <snapshot.tar.gz|basename> [--dir PATH] [--file PINS_FILE]"
      exit 0 ;;
    *)
      if [[ -z "$artifact" ]]; then artifact="$1"; shift
      else fail "unexpected arg: $1"
      fi
      ;;
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

[[ -n "$artifact" ]] || fail "missing artifact (tarball path or basename)"
base="$(basename "$artifact")"

[[ -f "$pins_file" ]] || { echo "OK: not pinned (pins file absent): $base"; exit 0; }

tmp="$(mktemp)"
grep -Fvx "$base" "$pins_file" > "$tmp" || true
mv "$tmp" "$pins_file"
echo "OK: unpinned (or not present): $base"
