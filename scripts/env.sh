#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root relative to this script (works on any machine/path).
REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

# Load per-machine overrides if present (NOT committed).
# Note: .env is treated as "trusted local config" (shell-compatible KEY=VALUE lines).
if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  source "${REPO_ROOT}/.env"
  set +a
fi

# Defaults (safe for local-only Ollama)
: "${OLLAMA_HOST:=http://127.0.0.1:11434}"

# Common repo-relative paths (avoid absolute, machine-specific values)
: "${LOG_DIR:=${REPO_ROOT}/logs}"
: "${EXPORT_DIR:=${REPO_ROOT}/exports}"

export REPO_ROOT OLLAMA_HOST LOG_DIR EXPORT_DIR
