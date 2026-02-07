import json, sys, urllib.request, urllib.parse

BASE = "http://127.0.0.1:8787"
IDENT = "S-001"
NOTE = "demo: moved to analyzing"

def req(method, path, payload=None):
    url = BASE + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))

# 1) Post status with note
out = req("POST", "/sample/status", {"identifier": IDENT, "status": "analyzing", "note": NOTE})
assert out.get("ok") is True, out
assert out.get("event_recorded") is True, out

# 2) Fetch events and find latest status_changed
ev = req("GET", "/sample/events?" + urllib.parse.urlencode({"identifier": IDENT, "limit": 20}))
assert ev.get("ok") is True, ev
events = ev.get("events") or []
sc = next((e for e in events if e.get("event_type") == "status_changed"), None)
assert sc is not None, events
assert sc.get("note") == NOTE, sc

print("OK: note persisted on latest status_changed event")
