#!/usr/bin/env bash
set -euo pipefail

fail() { echo "ERROR: $*" >&2; exit 2; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

n=1
dir="${EXPORTS_DIR:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --n)
      [[ $# -ge 2 ]] || fail "--n requires a value"
      n="$2"
      shift 2
      ;;
    --dir)
      [[ $# -ge 2 ]] || fail "--dir requires a value"
      dir="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: ./scripts/lims.sh snapshot latest [--n N] [--dir PATH]"
      echo "  Prints the Nth newest snapshot tarball path (default N=1)."
      echo "  Directory resolution order: --dir, EXPORTS_DIR, ./exports"
      exit 0
      ;;
    *)
      fail "unknown arg: $1"
      ;;
  esac
done

[[ "$n" =~ ^[1-9][0-9]*$ ]] || fail "--n must be a positive integer"

if [[ -z "$dir" ]]; then
  if [[ -d "$REPO_ROOT/exports" ]]; then
    dir="$REPO_ROOT/exports"
  else
    fail "EXPORTS_DIR not set and ./exports not found (use --dir PATH)"
  fi
fi

[[ "$dir" == /* ]] || dir="$REPO_ROOT/$dir"

mapfile -t files < <(
  find "$dir" -maxdepth 1 -type f \( -name 'snapshot-*.tar.gz' -o -name 'snapshot-*.tgz' \) -printf '%f\n' 2>/dev/null | sort -r
)

[[ ${#files[@]} -gt 0 ]] || fail "no snapshot tarballs found in: $dir"
(( n <= ${#files[@]} )) || fail "--n out of range: requested $n but only ${#files[@]} snapshot tarballs found"

pick="${files[$((n-1))]}"
echo "$dir/$pick"
