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

def wait_health(proc, base, tries=100):
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
    tmp = Path(tempfile.mkdtemp(prefix="nexus-api-sample-read-"))
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

        ext = "API-READ-001"
        st, j = http_json("POST", base + "/sample/add",
                          {"external_id": ext, "specimen_type": "saliva", "container": barcode})
        assert_true(st == 200 and j.get("ok") is True, f"/sample/add failed: {st} {j}")

        st, j = http_json("GET", base + "/sample/list?limit=50")
        assert_true(st == 200 and j.get("schema") == "nexus_sample_list" and j.get("ok") is True,
                    f"/sample/list bad: {st} {j}")
        items = j.get("samples") or []
        assert_true(any(isinstance(x, dict) and x.get("external_id") == ext for x in items),
                    "expected sample in /sample/list")

        st, j = http_json("GET", base + "/sample/show?identifier=" + ext)
        assert_true(st == 200 and j.get("schema") == "nexus_sample" and j.get("ok") is True,
                    f"/sample/show bad: {st} {j}")
        sample = j.get("sample") or {}
        assert_true(sample.get("external_id") == ext, "show: external_id mismatch")
        c = sample.get("container") or {}
        assert_true(c.get("barcode") == barcode, "show: container barcode mismatch")

        st, j = http_json("GET", base + "/sample/events?identifier=" + ext + "&limit=100")
        assert_true(st == 200 and j.get("schema") == "nexus_sample_events" and j.get("ok") is True,
                    f"/sample/events bad: {st} {j}")

        # contract checks for errors
        st, j = http_json("GET", base + "/sample/show?identifier=DOES-NOT-EXIST")
        assert_true(st == 404 and j.get("schema") == "nexus_api_error" and j.get("ok") is False,
                    "show not_found contract mismatch")

        st, j = http_json("GET", base + "/sample/list?limit=-1")
        assert_true(st == 400 and j.get("schema") == "nexus_api_error" and j.get("ok") is False,
                    "list bad limit contract mismatch")

        print("OK: API sample read endpoints regression passed.")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            pass

if __name__ == "__main__":
    main()
