#!/usr/bin/env bash
set -euo pipefail

main() {
  run() {
    local s="$1"
    echo
    echo "-> $s"
    if [[ "$s" == *.py ]]; then
      python3 "$s"
    else
      "$s"
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
  ./scripts/regress_snapshot_verify_json.py
  run ./scripts/regress_snapshot_doctor.py
  run ./scripts/regress_snapshot_diff.py
  run ./scripts/regress_snapshot_latest.py
  run ./scripts/regress_snapshot_diff_latest.py
  run ./scripts/regress_snapshot_prune.py
  run ./scripts/regress_snapshot_gc.py

  echo
  echo "OK: core regressions all green."
}

main "$@"
