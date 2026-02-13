#!/usr/bin/env bash
set -Eeuo pipefail

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

# 3) Guest auth should return a session token (string or session.id)
auth_json="$(curl "${curl_common[@]}" -X POST "$BASE_URL/auth/guest" || true)"

token="$(
  python3 - <<'PY' "$auth_json" 2>/dev/null || true
import json,sys
s=sys.argv[1]
try:
  j=json.loads(s)
except Exception:
  print("")
  raise SystemExit(0)

def pick_token(x):
  # Accept either a string token, or an object with {"id": "..."}
  if isinstance(x, str) and x.strip():
    return x.strip()
  if isinstance(x, dict):
    v = x.get("id")
    if isinstance(v, str) and v.strip():
      return v.strip()
  return ""

candidates = []
candidates.append(pick_token(j.get("session")))
candidates.append(pick_token((j.get("data") or {}).get("session")))
for k in ("session_id", "token"):
  candidates.append(pick_token(j.get(k)))
  candidates.append(pick_token((j.get("data") or {}).get(k)))

for t in candidates:
  if t:
    print(t)
    break
else:
  print("")
PY
)"

[[ -n "${token:-}" ]] || fail "/auth/guest returned no session token. Raw: $auth_json"
pass "/auth/guest returned session token"

# 4) sample/list should succeed with session header
code_samples="$(curl "${curl_common[@]}" -o /dev/null -w '%{http_code}' -H "X-Nexus-Session: $token" "$BASE_URL/sample/list" || true)"
[[ "$code_samples" == "200" ]] || fail "/sample/list expected 200 with session, got $code_samples"
pass "/sample/list ok with session (200)"

echo "PASS: ui_smoke"
