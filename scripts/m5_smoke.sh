#!/usr/bin/env bash
set -Eeuo pipefail

BASE_URL="${BASE_URL:-https://127.0.0.1}"
CURL=(curl -k -sS)

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "OK: $*"; }

post_json() {
  local url="$1"; shift
  local body="$1"; shift
  "${CURL[@]}" -X POST -H "Content-Type: application/json" -d "$body" "$url" "$@"
}

pick_session_id() {
  python3 - <<'PY' "$1" 2>/dev/null || true
import json,sys
s=sys.argv[1]
try:
  j=json.loads(s)
except Exception:
  print(""); raise SystemExit(0)

def pick(x):
  if isinstance(x,str) and x.strip(): return x.strip()
  if isinstance(x,dict):
    v=x.get("id")
    if isinstance(v,str) and v.strip(): return v.strip()
  return ""

cands=[]
cands.append(pick(j.get("session")))
cands.append(pick((j.get("data") or {}).get("session")))
for k in ("session_id","token"):
  cands.append(pick(j.get(k)))
  cands.append(pick((j.get("data") or {}).get(k)))
for t in cands:
  if t:
    print(t); break
else:
  print("")
PY
}

echo "== m5_smoke: BASE_URL=$BASE_URL =="

# 1) Guest session
auth_json="$(post_json "$BASE_URL/auth/guest" '{}')"
sid="$(pick_session_id "$auth_json")"
[[ -n "${sid:-}" ]] || fail "/auth/guest no session id. Raw: $auth_json"
pass "/auth/guest session ok"

H=( -H "X-Nexus-Session: $sid" )

# 2) Create container
barcode="CNT-$(date +%s)-$RANDOM"
body_container="$(printf '{"barcode":"%s","kind":"tube","location":"bench-A"}' "$barcode")"
cjson="$(post_json "$BASE_URL/container/add" "$body_container" "${H[@]}")"
echo "$cjson" | python3 -c 'import sys,json; j=json.load(sys.stdin); assert j.get("ok") is True; print(j.get("container",{}).get("id",""))' >/tmp/m5_container_id.txt \
  || fail "/container/add bad response: $cjson"
cid="$(cat /tmp/m5_container_id.txt)"
[[ -n "${cid:-}" ]] || fail "/container/add missing container id. Raw: $cjson"
pass "/container/add ok (id=$cid barcode=$barcode)"

# 3) List containers
ljson="$("${CURL[@]}" "$BASE_URL/container/list?limit=10" "${H[@]}")"
echo "$ljson" | python3 -c 'import sys,json; j=json.load(sys.stdin); assert j.get("ok") is True' \
  || fail "/container/list bad response: $ljson"
pass "/container/list ok"

# 4) Show container by barcode
sjson="$("${CURL[@]}" "$BASE_URL/container/show?barcode=$barcode" "${H[@]}")"
echo "$sjson" | python3 -c 'import sys,json; j=json.load(sys.stdin); assert j.get("ok") is True' \
  || fail "/container/show bad response: $sjson"
pass "/container/show ok"

# 5) Create sample linked to container
external="SMP-$(date +%s)-$RANDOM"
body_sample="$(printf '{"external_id":"%s","specimen_type":"blood","container":"%s","notes":"m5 smoke"}' "$external" "$barcode")"
samp_json="$(post_json "$BASE_URL/sample/add" "$body_sample" "${H[@]}")"
echo "$samp_json" | python3 -c 'import sys,json; j=json.load(sys.stdin); assert j.get("ok") is True; print(j.get("sample",{}).get("id",""))' >/tmp/m5_sample_id.txt \
  || fail "/sample/add bad response: $samp_json"
sid2="$(cat /tmp/m5_sample_id.txt)"
[[ -n "${sid2:-}" ]] || fail "/sample/add missing sample id. Raw: $samp_json"
pass "/sample/add ok (id=$sid2 external_id=$external)"

# 6) Append event
body_ev='{"identifier":"'"$external"'","event_type":"note","note":"hello from m5_smoke"}'
ev_json="$(post_json "$BASE_URL/sample/event" "$body_ev" "${H[@]}")"
echo "$ev_json" | python3 -c 'import sys,json; j=json.load(sys.stdin); assert j.get("ok") is True' \
  || fail "/sample/event bad response: $ev_json"
pass "/sample/event ok"

echo "PASS: m5_smoke"
