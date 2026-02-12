#!/usr/bin/env bash
# Interactive-safe + idempotent launcher.
# - Explicitly DISABLE errexit (handles inherited SHELLOPTS from strict interactive shells)
# - If already running (same app on same port), print status and exit 0
# - If port is used by something else, print details and exit 1 (no terminal-killing behavior)
set +o errexit 2>/dev/null || true
set +o errtrace 2>/dev/null || true
set -u
set -o pipefail

VENV="${VENV:-$HOME/.venvs/nexus-lab-tracker}"
PORT="${PORT:-8789}"
HOST="${HOST:-127.0.0.1}"
LOG="${LOG:-/tmp/nexus-fastapi-${PORT}-$(date +%Y%m%d-%H%M%S).log}"
PIDFILE="${PIDFILE:-/tmp/nexus-fastapi-${PORT}.pid}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing required command: $1"; return 1; }; }

need ss || exit 1
need curl || exit 1
need rg || exit 1

if [ ! -x "$VENV/bin/uvicorn" ]; then
  echo "missing uvicorn in venv: $VENV"
  echo "hint: $VENV/bin/python -m pip install fastapi uvicorn"
  exit 1
fi

# If pidfile exists but PID is dead, remove it
if [ -s "$PIDFILE" ]; then
  oldpid="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [ -n "${oldpid:-}" ] && ! kill -0 "$oldpid" 2>/dev/null; then
    rm -f "$PIDFILE" 2>/dev/null || true
  fi
fi

# If port is already in use, decide whether it's "ours"
if ss -ltnp 2>/dev/null | rg -q ":${PORT}\b"; then
  echo "PORT IN USE: ${HOST}:${PORT}"
  ss -ltnp 2>/dev/null | rg ":${PORT}\b" || true

  pids="$(ss -ltnp 2>/dev/null | rg ":${PORT}\b" | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | sort -u | tr '\n' ' ')"
  # Try pidfile first, else first pid from ss
  cand=""
  if [ -s "$PIDFILE" ]; then
    pf="$(cat "$PIDFILE" 2>/dev/null || true)"
    if [ -n "${pf:-}" ] && printf "%s" "$pids" | rg -q "(^| )${pf}( |$)"; then
      cand="$pf"
    fi
  fi
  if [ -z "${cand:-}" ]; then
    cand="$(printf "%s" "$pids" | awk '{print $1}')"
  fi

  if [ -n "${cand:-}" ]; then
    cmd="$(ps -p "$cand" -o args= 2>/dev/null || true)"
    if printf "%s" "$cmd" | rg -q 'uvicorn .*lims\.api_fastapi:app'; then
      echo "ALREADY RUNNING pid=$cand"
      echo "URL: http://${HOST}:${PORT}"
      echo "health:"
      curl -fsS "http://${HOST}:${PORT}/health" 2>/dev/null || true
      exit 0
    fi

    echo "ERROR: port is in use by a different process (not lims.api_fastapi:app)."
    echo "pid=$cand cmd=$cmd"
    echo "Tip: stop your FastAPI instance with: PORT=${PORT} scripts/stop_fastapi.sh"
    exit 1
  fi

  echo "ERROR: port is in use but could not identify pid."
  exit 1
fi

# Start detached (does not tie lifecycle to your terminal)
nohup "$VENV/bin/uvicorn" lims.api_fastapi:app \
  --host "$HOST" --port "$PORT" --log-level warning \
  >"$LOG" 2>&1 &
pid=$!
echo "$pid" >"$PIDFILE"

echo "STARTED pid=$pid"
echo "LOG=$LOG"
echo "PIDFILE=$PIDFILE"

# Wait for readiness (best-effort; no hard fail)
for i in $(seq 1 120); do
  if curl -fsS "http://${HOST}:${PORT}/metrics" >/dev/null 2>&1; then
    echo "READY: http://${HOST}:${PORT}"
    echo "health:"
    curl -fsS "http://${HOST}:${PORT}/health" 2>/dev/null || true
    exit 0
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "uvicorn exited early; last log lines:"
    tail -n 120 "$LOG" || true
    rm -f "$PIDFILE" 2>/dev/null || true
    exit 1
  fi
  sleep 0.1
done

echo "WARN: server did not become ready yet. Check log:"
echo "$LOG"
exit 0
