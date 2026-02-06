#!/usr/bin/env bash
set -Eeuo pipefail

# Default behavior:
#  - run in CI (GitHub Actions sets CI=true and/or GITHUB_ACTIONS=true)
#  - otherwise skip unless explicitly enabled
if [[ "${CI:-}" != "true" && "${GITHUB_ACTIONS:-}" != "true" && "${JERBOA_WEBUI_HEADLESS:-}" != "1" ]]; then
  echo "SKIP: web UI headless status check (set JERBOA_WEBUI_HEADLESS=1 to run locally)"
  exit 0
fi

if ! command -v node >/dev/null 2>&1; then
  echo "SKIP: web UI headless status check (node not installed)"
  exit 0
fi

node scripts/regress_web_ui_status_headless.js
