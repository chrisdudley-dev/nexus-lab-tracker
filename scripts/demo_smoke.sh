#!/usr/bin/env bash
set -Eeuo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1}"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "OK: $*"; }

echo "== demo_smoke: BASE_URL=$BASE_URL =="

# 1) Service should be up (health)
health="$(curl -fsS "$BASE_URL/health")" || fail "health endpoint not reachable"
echo "$health" | rg -q '"ok":true' || fail "health ok!=true"
echo "$health" | rg -q '"git_rev":"' || fail "health missing git_rev"
pass "health ok + git_rev present"

# 2) Auth-required sample list should deny when no session header
# (If auth is disabled, this may return 200; treat that as a soft warning.)
code="$(curl -sS -o /dev/null -w '%{http_code}' "$BASE_URL/sample/list" || true)"
if [[ "$code" == "401" ]]; then
  pass "sample/list requires auth (401)"
elif [[ "$code" == "200" ]]; then
  echo "WARN: sample/list returned 200; auth may be disabled (NEXUS_REQUIRE_AUTH_FOR_SAMPLES=0?)" >&2
else
  fail "sample/list unexpected status: $code"
fi

# 3) Metrics should work on localhost if BASE_URL is localhost.
# If user points BASE_URL at LAN IP, metrics may be forbidden by nginx; that's fine.
mcode="$(curl -sS -o /dev/null -w '%{http_code}' "$BASE_URL/metrics" || true)"
if [[ "$BASE_URL" == "http://127.0.0.1" || "$BASE_URL" == "http://localhost" ]]; then
  [[ "$mcode" == "200" ]] || fail "metrics expected 200 on localhost, got $mcode"
  pass "metrics reachable on localhost"
else
  [[ "$mcode" == "403" || "$mcode" == "200" ]] || fail "metrics expected 403/200, got $mcode"
  pass "metrics policy acceptable for non-local BASE_URL (got $mcode)"
fi

echo "PASS: demo_smoke"
