#!/usr/bin/env python3
"""
Regression: guest auth endpoints.
- POST /auth/guest returns schema + session id
- GET /auth/me with X-Nexus-Session returns same session
- GET /auth/me without session returns 401
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


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def http_json(method: str, url: str, payload=None, headers=None, timeout: float = 2.0):
    data = None
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        hdrs["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return r.status, body
    except urllib.error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        return e.code, body


def main() -> int:
    port = free_port()
    env = os.environ.copy()
    # keep the test isolated from any accidental GH auth env
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)

    p = subprocess.Popen(
        [sys.executable, "scripts/lims_api.py", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
    )

    try:
        # wait for /health
        start = time.time()
        ready = False
        while time.time() - start < 6.0:
            try:
                st, _ = http_json("GET", f"http://127.0.0.1:{port}/health", timeout=0.6)
                if st == 200:
                    ready = True
                    break
            except Exception:
                pass
            time.sleep(0.12)

        if not ready:
            out = ""
            try:
                out = (p.stdout.read(2000) if p.stdout else "")
            except Exception:
                pass
            print("FAIL: API did not become ready for /health")
            if out:
                print("--- server output (partial) ---")
                print(out)
            return 2

        # create guest session
        st, body = http_json(
            "POST",
            f"http://127.0.0.1:{port}/auth/guest",
            payload={"display_name": "Guest"},
            timeout=1.8,
        )
        if st != 200:
            print(f"FAIL: POST /auth/guest status={st}")
            print(body.decode("utf-8", errors="replace"))
            return 2

        doc = json.loads(body.decode("utf-8"))
        if doc.get("schema") != "nexus_auth_guest" or doc.get("ok") is not True:
            print("FAIL: /auth/guest schema/ok mismatch")
            print(doc)
            return 2

        sess = doc.get("session") or {}
        sid = (sess.get("id") or "").strip()
        if not sid:
            print("FAIL: /auth/guest missing session.id")
            print(doc)
            return 2

        # /auth/me with session header
        st2, body2 = http_json(
            "GET",
            f"http://127.0.0.1:{port}/auth/me",
            headers={"X-Nexus-Session": sid},
            timeout=1.8,
        )
        if st2 != 200:
            print(f"FAIL: GET /auth/me status={st2}")
            print(body2.decode("utf-8", errors="replace"))
            return 2

        doc2 = json.loads(body2.decode("utf-8"))
        if doc2.get("schema") != "nexus_auth_me" or doc2.get("ok") is not True:
            print("FAIL: /auth/me schema/ok mismatch")
            print(doc2)
            return 2

        sess2 = doc2.get("session") or {}
        if (sess2.get("id") or "").strip() != sid:
            print("FAIL: /auth/me session id mismatch")
            print("expected:", sid)
            print("got:", sess2.get("id"))
            return 2

        # /auth/me without session -> 401
        st3, body3 = http_json("GET", f"http://127.0.0.1:{port}/auth/me", timeout=1.8)
        if st3 != 401:
            print(f"FAIL: /auth/me without session expected 401, got {st3}")
            print(body3.decode("utf-8", errors="replace"))
            return 2

        print("OK: guest auth regression passed.")
        return 0

    finally:
        try:
            p.terminate()
        except Exception:
            pass
        try:
            p.wait(timeout=2.0)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
