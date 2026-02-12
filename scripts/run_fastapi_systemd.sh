#!/usr/bin/env bash
set +o errexit 2>/dev/null || true
set +u

REPO_ROOT="${REPO_ROOT:-/mnt/ssd/projects/nexus-lab-tracker}"
VENV="${VENV:-/home/christopher/.venvs/nexus-lab-tracker}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8789}"

cd "$REPO_ROOT" || exit 1
exec "$VENV/bin/uvicorn" lims.api_fastapi:app --host "$HOST" --port "$PORT" --log-level info
