#!/usr/bin/env bash
set -euo pipefail
fail(){ echo "ERROR: $*" >&2; exit 2; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

dir="${EXPORTS_DIR:-}"
pins_file=""
n=""
artifact=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) [[ $# -ge 2 ]] || fail "--dir requires a value"; dir="$2"; shift 2 ;;
    --file) [[ $# -ge 2 ]] || fail "--file requires a value"; pins_file="$2"; shift 2 ;;
    --n) [[ $# -ge 2 ]] || fail "--n requires a value"; n="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: ./scripts/lims.sh snapshot pin <snapshot.tar.gz|basename> [--dir PATH] [--file PINS_FILE]"
      echo "   or: ./scripts/lims.sh snapshot pin --n N [--dir PATH] [--file PINS_FILE]"
      echo "  Pins a snapshot tarball (by basename). Prune will never delete pinned snapshots."
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

if [[ -n "$n" ]]; then
  [[ "$n" =~ ^[1-9][0-9]*$ ]] || fail "--n must be a positive integer"
  artifact="$(./scripts/snapshot_latest.sh --n "$n" --dir "$dir")"
fi

[[ -n "$artifact" ]] || fail "missing artifact (pass tarball/basename or use --n N)"

base="$(basename "$artifact")"
case "$base" in
  snapshot-*.tar.gz|snapshot-*.tgz) ;;
  *) fail "not a snapshot tarball name: $base" ;;
esac

mkdir -p "$(dirname "$pins_file")"
touch "$pins_file"

if grep -Fxq "$base" "$pins_file"; then
  echo "OK: already pinned: $base"
  exit 0
fi

printf "%s\n" "$base" >> "$pins_file"
echo "OK: pinned: $base"
