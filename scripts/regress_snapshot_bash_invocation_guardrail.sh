#!/usr/bin/env bash
set -euo pipefail

echo "== regress: snapshot scripts invoked via bash (no direct ./scripts/snapshot_*.sh) =="

bad="$(
  git ls-files scripts .github 2>/dev/null \
  | rg -n --no-mmap --threads 1 \
      '(^|[[:space:];(&|])\./scripts/snapshot_[A-Za-z0-9_]+\.sh([[:space:];)|&]|$)' \
  | rg -v --no-mmap --threads 1 '(^|[[:space:];(&|])bash[[:space:]]+\./scripts/snapshot_' \
  | rg -v --no-mmap --threads 1 '(^|[[:space:];(&|])exec[[:space:]]+bash[[:space:]]+' \
  | rg -v --no-mmap --threads 1 '\["bash",[[:space:]]*"\./scripts/snapshot_' \
  || true
)"

if [ -n "$bad" ]; then
  echo "ERROR: Found direct snapshot_*.sh execution (must be via bash):"
  echo "$bad"
  exit 1
fi

echo "OK: no direct snapshot_*.sh execution detected."
