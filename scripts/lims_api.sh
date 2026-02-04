#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.." || exit 1
exec python3 scripts/lims_api.py "$@"
