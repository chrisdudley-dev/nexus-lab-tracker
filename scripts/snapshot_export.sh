#!/usr/bin/env bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/env.sh"

mkdir -p "${EXPORT_DIR}"
echo "Repo: ${REPO_ROOT}"
echo "Export dir: ${EXPORT_DIR}"
echo "TODO: implement snapshot/export workflow."
