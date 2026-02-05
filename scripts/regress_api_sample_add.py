#!/usr/bin/env python3
import json, os, socket, subprocess, tempfile, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

REPO_ROOT = Path(__file__).resolve().parents[1]

def run(cmd, env, check=True):
    p = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and p.returncode != 0:
        raise SystemExit(
            "FAIL cmd: %s\nSTDOUT:\n%s\nSTDERR:\n%s"
            % (" ".join(cmd), p.stdout, p.stderr)
        )
    return p

def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port

def http_json(method, url, body=None):
    data = None
    headers = {}
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = Request(url, method=method, data=data, headers=headers)
    with urlopen(req, timeout=8) as r:
        return r.status, r.read(), dict(r.headers)

def wait_health(proc, base, tries=80):
    for _ in range(tries):
        rc = proc.poll()
        if rc is not None:
            err = ""
            try:
                if proc.stderr:
                    err = proc.stderr.read() or ""
            except Exception:
                pass
            raise SystemExit(f"FAIL: API exited early rc={rc}\n{err}")
        try:
            st, _, _ = http_json("GET", base + "/health")
            if st == 200:
                return
        except Exception:
            time.sleep(0.1)
    raise SystemExit("FAIL: API did not become healthy in time")

def main():
    tmp = Path(tempfile.mkdtemp(prefix="nexus-api-sample-add-"))
    db_path = tmp / "lims.sqlite3"

    env = os.environ.copy()
    env["DB_PATH"] = str(db_path)

    # schema
    run(["./scripts/lims.sh", "init"], env)
    run(["./scripts/migrate.sh", "up"], env)

    port = free_port()
    proc = subprocess.Popen(
        [os.sys.executable, "scripts/lims_api.py", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"

    try:
        wait_health(proc, base)

        # 1) Create sample (explicit external_id for determinism)
        payload = {"external_id": "API-001", "specimen_type": "saliva"}
        st, raw, _ = http_json("POST", base + "/sample/add", payload)
        if st != 200:
            raise SystemExit(f"FAIL: POST /sample/add status={st} body={raw[:500]!r}")

        doc = json.loads(raw.decode("utf-8", errors="replace"))
        # envelope assertions
        if doc.get("schema") != "nexus_sample":
            raise SystemExit(f"FAIL: schema expected nexus_sample got: {doc.get('schema')}")
        if doc.get("schema_version") != 1:
            raise SystemExit(f"FAIL: schema_version expected 1 got: {doc.get('schema_version')}")
        if doc.get("ok") is not True:
            raise SystemExit(f"FAIL: ok expected true got: {doc.get('ok')}")

        if "generated_at" not in doc or "sample" not in doc or not isinstance(doc["sample"], dict):
            raise SystemExit(f"FAIL: unexpected response shape: {doc}")

        sample = doc["sample"]
        if sample.get("external_id") != "API-001":
            raise SystemExit(f"FAIL: external_id mismatch: {sample.get('external_id')}")
        if sample.get("specimen_type") != "saliva":
            raise SystemExit(f"FAIL: specimen_type mismatch: {sample.get('specimen_type')}")
        if sample.get("status") != "received":
            raise SystemExit(f"FAIL: status expected 'received' got: {sample.get('status')}")

        # 2) Duplicate external_id should fail (400)
        try:
            http_json("POST", base + "/sample/add", payload)
            raise SystemExit("FAIL: duplicate external_id unexpectedly succeeded")
        except HTTPError as e:
            if e.code != 400:
                body = e.read()
                raise SystemExit(f"FAIL: expected 400 for dup external_id, got {e.code} body={body[:500]!r}")

        print("OK: /sample/add creates sample and rejects duplicate external_id.")
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
    main()
