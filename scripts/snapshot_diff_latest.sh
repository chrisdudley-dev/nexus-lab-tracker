#!/usr/bin/env bash
set -euo pipefail

fail() { echo "ERROR: $*" >&2; exit 2; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

n=2
dir=""
no_migrate=0
json_only=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --n)
      [[ $# -ge 2 ]] || fail "--n requires a value"
      n="$2"; shift 2
      ;;
    --dir)
      [[ $# -ge 2 ]] || fail "--dir requires a value"
      dir="$2"; shift 2
      ;;
    --no-migrate) no_migrate=1; shift ;;
    --json-only)  json_only=1; shift ;;
    -h|--help)
      echo "Usage: ./scripts/lims.sh snapshot diff-latest [--n N] [--dir PATH] [--no-migrate] [--json-only]"
      echo "  Diffs newest snapshot (N=1) against the Nth newest (default N=2)."
      echo "  Uses snapshot tarballs found in: --dir, EXPORTS_DIR, or ./exports"
      exit 0
      ;;
    *) fail "unknown arg: $1" ;;
  esac
done

[[ "$n" =~ ^[1-9][0-9]*$ ]] || fail "--n must be a positive integer"

latest_args=()
[[ -n "$dir" ]] && latest_args+=(--dir "$dir")

A="$(./scripts/snapshot_latest.sh --n "$n" "${latest_args[@]}")"
B="$(./scripts/snapshot_latest.sh --n 1   "${latest_args[@]}")"

flags=()
(( no_migrate )) && flags+=(--no-migrate)
(( json_only ))  && flags+=(--json-only)

exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/snapshot_diff.py" "$A" "$B" "${flags[@]}"
