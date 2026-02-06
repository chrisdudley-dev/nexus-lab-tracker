#!/usr/bin/env python3
import json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

REPO_ROOT = Path(__file__).resolve().parents[1]

def run(cmd, env, check=True):
    p = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise SystemExit(f"FAIL cmd: {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
    return p

def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port

def http_json(method, url, body=None):
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = Request(url, method=method, data=data, headers=headers)
    try:
        with urlopen(req, timeout=10) as r:
            raw = r.read()
            return r.status, json.loads(raw.decode("utf-8", errors="replace"))
    except HTTPError as e:
        raw = e.read()
        try:
            j = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            j = {"raw": raw.decode("utf-8", errors="replace")}
        return e.code, j

def assert_true(cond, msg):
    if not cond:
        raise SystemExit("FAIL: " + msg)

def wait_health(proc, base, tries=120):
    for _ in range(tries):
        if proc.poll() is not None:
            raise SystemExit("FAIL: API exited early")
        try:
            st, j = http_json("GET", base + "/health")
            if st == 200 and isinstance(j, dict) and j.get("ok") is True:
                return
        except Exception:
            pass
        time.sleep(0.1)
    raise SystemExit("FAIL: API did not become healthy in time")

def main():
    tmp = Path(tempfile.mkdtemp(prefix="nexus-api-sample-status-"))
    db_path = tmp / "lims.sqlite3"

    env = os.environ.copy()
    env["DB_PATH"] = str(db_path)

    run(["./scripts/lims.sh", "init"], env)
    run(["./scripts/migrate.sh", "up"], env)

    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "scripts/lims_api.py", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(REPO_ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True,
    )
    base = f"http://127.0.0.1:{port}"

    try:
        wait_health(proc, base)

        barcode = f"API-TUBE-{int(time.time())}"
        st, j = http_json("POST", base + "/container/add",
                          {"barcode": barcode, "kind": "tube", "location": "bench-A"})
        assert_true(st == 200 and j.get("ok") is True, f"/container/add failed: {st} {j}")

        ext = "API-STATUS-001"
        st, j = http_json("POST", base + "/sample/add",
                          {"external_id": ext, "specimen_type": "saliva", "container": barcode})
        assert_true(st == 200 and j.get("ok") is True, f"/sample/add failed: {st} {j}")

        # status update
        st, j = http_json("POST", base + "/sample/status",
                          {"identifier": ext, "status": "processing", "message": "start processing"})
        assert_true(st == 200 and j.get("schema") == "nexus_sample_status_update" and j.get("ok") is True,
                    f"/sample/status bad: {st} {j}")

        # alias -> canonical
        st, j = http_json("POST", base + "/sample/status",
                          {"identifier": ext, "status": "analysis", "message": "alias should map to analyzing"})
        assert_true(st == 200 and j.get("schema") == "nexus_sample_status_update" and j.get("ok") is True,
                    f"/sample/status alias bad: {st} {j}")

        # show reflects status if exposed by schema
        st, j = http_json("GET", base + "/sample/show?identifier=" + ext)
        assert_true(st == 200 and j.get("schema") == "nexus_sample" and j.get("ok") is True,
                    f"/sample/show after status bad: {st} {j}")
        sample = (j.get("sample") or {})
        if isinstance(sample, dict) and "status" in sample:
            assert_true(sample.get("status") in ("processing", "analyzing", "completed", "received"),
                        f"unexpected sample.status: {sample.get('status')}")

        # events endpoint should still work (event recording is best-effort)
        st, j = http_json("GET", base + "/sample/events?identifier=" + ext + "&limit=50")
        assert_true(st == 200 and j.get("schema") == "nexus_sample_events" and j.get("ok") is True,
                    f"/sample/events bad: {st} {j}")

        # invalid status -> 400 error envelope
        st, j = http_json("POST", base + "/sample/status",
                          {"identifier": ext, "status": "not-a-real-status"})
        assert_true(st == 400 and j.get("schema") == "nexus_api_error" and j.get("ok") is False,
                    f"invalid status should be 400 nexus_api_error: {st} {j}")

        # missing identifier -> 400 error envelope
        st, j = http_json("POST", base + "/sample/status",
                          {"status": "processing"})
        assert_true(st == 400 and j.get("schema") == "nexus_api_error" and j.get("ok") is False,
                    f"missing identifier should be 400 nexus_api_error: {st} {j}")

        print("OK: API sample status regression passed.")

    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            pass

if __name__ == "__main__":
    main()
