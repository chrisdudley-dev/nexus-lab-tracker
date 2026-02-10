#!/usr/bin/env python3
"""
Regression: optional auth enforcement for /sample/* endpoints.

When NEXUS_REQUIRE_AUTH_FOR_SAMPLES=1:
- /sample/list should be 401 without session
- /auth/guest returns a session
- /sample/list should be 200 with X-Nexus-Session
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error

REPO_ROOT = os.environ.get("REPO_ROOT", os.getcwd())
PYTHON = sys.executable


def pick_free_port() -> int:
    # Ask OS for an available port to avoid collisions with other regressions/services.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def http_json(method: str, url: str, body: dict | None = None, headers: dict | None = None):
    data = None
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read()
            ct = (r.headers.get("content-type") or "").lower()
            if "application/json" in ct:
                return r.status, json.loads(raw.decode("utf-8", errors="replace"))
            return r.status, raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            doc = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            doc = {"ok": False, "raw": raw[:200].decode("utf-8", errors="replace")}
        return e.code, doc
    except urllib.error.URLError as e:
        # Server not up yet / connection refused / transient network errors.
        return 0, {"ok": False, "error": "connect", "detail": str(e)}


def wait_health(base: str, proc: subprocess.Popen, tries: int = 120):
    for _ in range(tries):
        if proc.poll() is not None:
            out = ""
            try:
                if proc.stdout:
                    out = proc.stdout.read() or ""
            except Exception:
                pass
            raise SystemExit(f"FAIL: API process exited early (rc={proc.returncode}). Output:\n{out[-2000:]}")
        st, j = http_json("GET", base + "/health")
        if st == 200 and isinstance(j, dict) and j.get("ok") is True:
            return
        time.sleep(0.1)
    raise SystemExit("FAIL: API /health never became ready")


def main() -> int:
    env = os.environ.copy()
    env["NEXUS_REQUIRE_AUTH_FOR_SAMPLES"] = "1"
    env["PYTHONUNBUFFERED"] = "1"

    port = str(pick_free_port())
    base = f"http://127.0.0.1:{port}"

    cmd = [PYTHON, os.path.join(REPO_ROOT, "scripts", "lims_api.py"), "--port", port]
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    try:
        wait_health(base, proc)

        # 1) sample list without session => 401
        st, j = http_json("GET", base + "/sample/list?limit=1")
        if st != 401:
            raise SystemExit(f"FAIL: expected 401 for /sample/list without session, got {st} {j}")

        # 2) create guest session
        st, j = http_json("POST", base + "/auth/guest", {"display_name": "Guest"})
        if st != 200 or not isinstance(j, dict) or j.get("ok") is not True:
            raise SystemExit(f"FAIL: /auth/guest failed: status={st} body={j}")
        sid = ((j.get("session") or {}).get("id") or "").strip()
        if not sid:
            raise SystemExit("FAIL: /auth/guest missing session.id")

        # 3) sample list with session => 200
        st, j = http_json("GET", base + "/sample/list?limit=1", headers={"X-Nexus-Session": sid})
        if st != 200 or not isinstance(j, dict) or j.get("ok") is not True:
            raise SystemExit(f"FAIL: expected 200 for /sample/list with session, got {st} {j}")

        print("OK: auth samples opt-in regression passed.")
        return 0
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
