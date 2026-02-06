#!/usr/bin/env bash
set -euo pipefail

# Integrity guard (catches paste-garble / truncation early)
grep -q 'PASTE_GARBAGE_GUARD' "$0" || { echo 'ERROR: corrupted regress_core.sh (missing PASTE_GARBAGE_GUARD)' >&2; exit 2; }
grep -q 'API_REGRESS' "$0" || { echo 'ERROR: corrupted regress_core.sh (missing API_REGRESS)' >&2; exit 2; }


main() {
  run() {
    if [[ $# -lt 1 ]]; then
      echo "ERROR: run() called with no args" >&2
      return 2
    fi
    echo
    echo "-> $*"
    if [[ $# -eq 1 && "$1" == *.py ]]; then
      python3 "$1"
    else
      "$@"
    fi
  }

  echo "== Core Regressions =="

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
  run ./scripts/regress_sample_report.py
  run ./scripts/regress_sample_export.py
  run ./scripts/regress_snapshot_include_sample.py

  # 5) Sample move safety precheck
  run ./scripts/regress_sample_move_precheck.py

  # 6) Snapshot export + restore (round-trip)
  run ./scripts/regress_snapshot_export.py
  run ./scripts/regress_snapshot_manifest.py
  run ./scripts/regress_snapshot_restore.py
  run ./scripts/regress_snapshot_verify.py
  run ./scripts/regress_snapshot_tar_unsafe_entries.py
  run ./scripts/regress_snapshot_verify_json.py
  run ./scripts/regress_snapshot_doctor.py
  run ./scripts/regress_snapshot_diff.py
  run ./scripts/regress_snapshot_latest.py
  run ./scripts/regress_snapshot_diff_latest.py
  run ./scripts/regress_snapshot_prune.py
  run ./scripts/regress_snapshot_gc.py

  echo
  run bash ./scripts/regress_snapshot_bash_invocation_guardrail.sh
  echo "OK: core regressions all green."
}

main "$@"

# PASTE_GARBAGE_GUARD
bash scripts/regress_no_paste_garbage.sh

# API_REGRESS
python3 scripts/regress_api_sample_add.py
python3 scripts/regress_api_sample_read_endpoints.py
python3 scripts/regress_api_sample_status_post.py
python3 scripts/regress_api_snapshot_export_verify.py
./scripts/regress_api_container_workflow.py
