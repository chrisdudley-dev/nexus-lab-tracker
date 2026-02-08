#!/usr/bin/env python3
"""
Regression: GET /metrics returns Prometheus plaintext with key lines.
Assumes lims_api.py can be started locally on a free port.
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
import urllib.request

REQUIRED_PATTERNS = [
    r"^# HELP nexus_api_up\b",
    r"^# TYPE nexus_api_up\b",
    r"^nexus_api_up\s+1\s*$",
    r"^# HELP nexus_build_info\b",
    r"^# TYPE nexus_build_info\b",
    r'^nexus_build_info\{git_rev="[^"]+"\}\s+1\s*$',
    r"^# HELP nexus_db_up\b",
    r"^# TYPE nexus_db_up\b",
    r"^nexus_db_up\s+[01]\s*$",
    r"^# HELP nexus_samples_total\b",
    r"^# TYPE nexus_samples_total\b",
    r"^nexus_samples_total\s+\d+\s*$",
    r"^# HELP nexus_containers_total\b",
    r"^# TYPE nexus_containers_total\b",
    r"^nexus_containers_total\s+\d+\s*$",
    r"^# HELP nexus_sample_events_total\b",
    r"^# TYPE nexus_sample_events_total\b",
    r"^nexus_sample_events_total\s+\d+\s*$",
]

def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port

def http_get(url: str, timeout: float = 2.0) -> tuple[int, bytes, dict]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read(), dict(r.headers.items())

def main() -> int:
    port = free_port()
    env = os.environ.copy()
    # Ensure local runs don't accidentally inject GH_TOKEN or other surprises.
    env.pop("GH_TOKEN", None)

    p = subprocess.Popen(
        [sys.executable, "scripts/lims_api.py", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
    )

    try:
        # Wait for server to listen (best-effort)
        start = time.time()
        ready = False
        while time.time() - start < 5.0:
            try:
                status, body, headers = http_get(f"http://127.0.0.1:{port}/health", timeout=0.5)
                if status == 200:
                    ready = True
                    break
            except Exception:
                time.sleep(0.1)

        if not ready:
            out = ""
            try:
                out = (p.stdout.read(2000) if p.stdout else "")  # type: ignore
            except Exception:
                pass
            print("FAIL: API did not become ready for /health")
            if out:
                print("--- server output (partial) ---")
                print(out)
            return 2

        status, body, headers = http_get(f"http://127.0.0.1:{port}/metrics", timeout=1.5)
        if status != 200:
            print(f"FAIL: /metrics status={status}")
            return 2

        ct = (headers.get("Content-Type") or headers.get("content-type") or "").lower()
        if "text/plain" not in ct:
            print(f"FAIL: /metrics content-type unexpected: {ct!r}")
            return 2

        text = body.decode("utf-8", errors="replace")
        for pat in REQUIRED_PATTERNS:
            if not re.search(pat, text, flags=re.M):
                print(f"FAIL: missing pattern: {pat}")
                print("--- /metrics body ---")
                print(text)
                return 2

        print("OK: /metrics Prometheus plaintext regression passed.")
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
