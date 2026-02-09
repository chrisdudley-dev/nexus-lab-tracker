#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TS="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="${DEMO_PROOF_DIR:-$ROOT/report/demo_proof/$TS}"
LOG="$OUT_DIR/demo_smoke.log"

mkdir -p "$OUT_DIR"

{
  echo "== Nexus Lab Tracker: demo smoke =="
  echo "time: $(date -Is)"
  echo "branch: $(git -C "$ROOT" branch --show-current)"
  echo "commit: $(git -C "$ROOT" rev-parse --short HEAD)"
  echo

  echo "== system =="
  uname -a || true
  python3 --version || true
  echo

  echo "== core regressions =="
  cd "$ROOT"
  set +e
  ./scripts/regress_core.sh
  rc=$?
  set -e
  echo "regress_core_rc=$rc"
  echo

  if [[ "${JERBOA_WEBUI_HEADLESS:-0}" == "1" ]]; then
    echo "== web UI headless status (optional) =="
    set +e
    JERBOA_WEBUI_HEADLESS=1 ./scripts/regress_web_ui_status_headless.sh
    echo "webui_headless_rc=$?"
    set -e
    echo
  else
    echo "== web UI headless status =="
    echo "SKIP (set JERBOA_WEBUI_HEADLESS=1 to run)"
    echo
  fi

  echo "== demo checklist (manual) =="
  echo "1) Start API:"
  echo "   ./scripts/lims_api.sh            # default 127.0.0.1:8787"
  echo "   ./scripts/lims_api.sh --port 8087  # optional alternate (README example)"
  echo "2) Open UI in browser:"
  echo "   http://127.0.0.1:<PORT>/"
  echo "3) Verify endpoints:"
  echo "   /health  and  /metrics"
  echo "4) Workflow demo:"
  echo "   add container + add sample + move status w/ note + show audit/provenance signal"
  echo
  echo "proof_dir=$OUT_DIR"
} | tee "$LOG"

exit "${rc:-0}"
