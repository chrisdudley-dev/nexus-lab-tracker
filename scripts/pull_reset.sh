#!/usr/bin/env bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/env.sh"

echo "Repo: ${REPO_ROOT}"
echo "OLLAMA_HOST: ${OLLAMA_HOST}"
echo "TODO: implement pull/reset workflow safely."
