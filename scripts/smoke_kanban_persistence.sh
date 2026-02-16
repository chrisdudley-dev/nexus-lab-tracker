#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8788}"
echo "Using BASE_URL=$BASE_URL"

echo "== GET current board =="
curl -fsS "$BASE_URL/api/kanban/board" | head -c 300; echo

echo "== PUT board (move c1 -> done) =="
payload='{
  "columnOrder": ["todo", "doing", "done"],
  "columns": {
    "todo":  {"id":"todo","title":"To Do","cardIds":[]},
    "doing": {"id":"doing","title":"In Progress","cardIds":[]},
    "done":  {"id":"done","title":"Done","cardIds":["c1"]}
  },
  "cards": {"c1":{"id":"c1","title":"Example card","subtitle":"Persisted via /api/kanban/board"}}
}'
curl -fsS -X PUT "$BASE_URL/api/kanban/board" \
  -H 'Content-Type: application/json' \
  -d "$payload" | head -c 300; echo

echo "== GET verify =="
curl -fsS "$BASE_URL/api/kanban/board" | grep -q '"done".*"cardIds".*\["c1"\]' && echo "OK: persisted"
