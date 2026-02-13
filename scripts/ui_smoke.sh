#!/usr/bin/env bash
set -Eeuo pipefail

# Default to localhost HTTPS (self-signed). Override if needed:
#   BASE_URL="https://127.0.0.1" ./scripts/ui_smoke.sh
BASE_URL="${BASE_URL:-https://127.0.0.1}"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "OK: $*"; }

echo "== ui_smoke: BASE_URL=$BASE_URL =="

curl_common=( -k -sS )

# 1) UI should be reachable
code_ui="$(curl "${curl_common[@]}" -o /dev/null -w '%{http_code}' "$BASE_URL/ui/" || true)"
[[ "$code_ui" == "200" ]] || fail "/ui/ expected 200, got $code_ui"
pass "/ui/ reachable (200)"

# 2) Health should be ok
health="$(curl "${curl_common[@]}" "$BASE_URL/health" || true)"
echo "$health" | rg -q '"ok":true' || fail "/health ok!=true"
pass "/health ok:true"

# 3) Guest auth should return a token in some known field
auth_json="$(curl "${curl_common[@]}" -X POST "$BASE_URL/auth/guest" || true)"
# Try common shapes; keep it robust.
token="$(
  python3 - <<'PY' "$auth_json" 2>/dev/null || true
import json,sys
s=sys.argv[1]
try:
  j=json.loads(s)
except Exception:
  print("")
  raise SystemExit(0)
candidates=[
  j.get("session"),
  j.get("session_id"),
  j.get("token"),
  (j.get("data") or {}).get("session"),
  (j.get("data") or {}).get("token"),
]
for t in candidates:
  if isinstance(t,str) and t.strip():
    print(t.strip()); break
else:
  print("")
PY
)"
[[ -n "${token:-}" ]] || fail "/auth/guest returned no session token. Raw: $auth_json"
pass "/auth/guest returned session token"

# 4) sample/list should succeed with session header (auth enforced)
code_samples="$(curl "${curl_common[@]}" -o /dev/null -w '%{http_code}' -H "X-Nexus-Session: $token" "$BASE_URL/sample/list" || true)"
[[ "$code_samples" == "200" ]] || fail "/sample/list expected 200 with session, got $code_samples"
pass "/sample/list ok with session (200)"

echo "PASS: ui_smoke"
