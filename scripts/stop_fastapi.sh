#!/usr/bin/env bash
set -u

PORT="${PORT:-8789}"
PIDFILE="${PIDFILE:-/tmp/nexus-fastapi-${PORT}.pid}"

if [ ! -s "$PIDFILE" ]; then
  echo "No pidfile at $PIDFILE (nothing to stop)."
  exit 0
fi

pid="$(cat "$PIDFILE" 2>/dev/null || true)"
if [ -z "${pid:-}" ]; then
  echo "Empty pidfile: $PIDFILE"
  rm -f "$PIDFILE" || true
  exit 0
fi

if kill -0 "$pid" 2>/dev/null; then
  echo "Stopping pid=$pid ..."
  kill -TERM "$pid" 2>/dev/null || true

  # wait up to ~3s
  for i in $(seq 1 30); do
    if ! kill -0 "$pid" 2>/dev/null; then
      break
    fi
    sleep 0.1
  done

  if kill -0 "$pid" 2>/dev/null; then
    echo "Still running; sending KILL..."
    kill -KILL "$pid" 2>/dev/null || true
  fi
else
  echo "pid=$pid not running."
fi

rm -f "$PIDFILE" 2>/dev/null || true
echo "Stopped. (pidfile removed)"
