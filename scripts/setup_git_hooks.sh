#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

chmod +x .githooks/pre-push
chmod +x scripts/regress_core.sh

git config core.hooksPath .githooks
echo "OK: core.hooksPath set to $(git config --get core.hooksPath)"
