#!/usr/bin/env bash
set -euo pipefail

# Core regression suite: fast, deterministic, fail-fast.
# Run from repo root.

fail() { echo "FAIL: $*" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

if ! have python3; then fail "python3 not found"; fi

echo "== Core Regressions =="

run() {
  local s="$1"
  echo
  echo "-> $s"
  "$s"
}

# 1) Input/CLI contract regressions (cheap, fast)
run ./scripts/regress_list_container_whitespace_error.py
run ./scripts/regress_limit_semantics.py

# 2) Container exclusivity model (database + triggers + CLI)
run ./scripts/regress_container_exclusivity.py
run ./scripts/regress_container_set_exclusive.py

# 3) Kind defaults model (seed/list/set/apply/apply-all + guardrails)
run ./scripts/regress_container_kind_defaults_cli.py
run ./scripts/regress_container_kind_defaults_apply_all.py

# 4) Operator visibility/auditability tools
run ./scripts/regress_container_show.py
run ./scripts/regress_container_audit.py

# 5) Sample move safety precheck
run ./scripts/regress_sample_move_precheck.py

echo
echo "OK: core regressions all green."
