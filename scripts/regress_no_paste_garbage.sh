#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

fail=0

# Scan only "real" scripts (exclude backups/patch artifacts and this script itself)
GREP_BASE=(
  grep -RIn
  --exclude-dir=.git
  --exclude='regress_no_paste_garbage.sh'
  --exclude='*.bak.*' --exclude='*.orig' --exclude='*.rej'
  --include='*.sh' --include='*.py'
)

# High-signal corruption markers observed in sessions (keep these specific to avoid false positives)
markers=(
  'PYint\('
  'EOFint\('
  'sys\.exitgrep'
)

for pat in "${markers[@]}"; do
  if "${GREP_BASE[@]}" -E "$pat" scripts >/dev/null 2>&1; then
    echo "FAIL: found paste-corruption marker regex: $pat" >&2
    "${GREP_BASE[@]}" -E "$pat" scripts >&2 || true
    fail=1
  fi
done

if (( fail )); then
  exit 2
fi

echo "OK: no high-signal paste-corruption markers detected."
