#!/usr/bin/env python3
import json, os, socket, subprocess, tempfile, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

REPO_ROOT = Path(__file__).resolve().parents[1]

def run(cmd, env, check=True):
    p = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(f"FAIL cmd: {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
    return p

def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port

def http_json(method, url, body=None, timeout=6):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        try:
            return e.code, json.loads(raw) if raw else {}
        except Exception:
            return e.code, {"_raw": raw}

def assert_api_error(status, doc, error):
    if doc.get("schema") != "nexus_api_error" or doc.get("schema_version") != 1 or doc.get("ok") is not False:
        raise RuntimeError(f"FAIL: expected nexus_api_error schema, got status={status} doc={doc}")
    if doc.get("error") != error:
        raise RuntimeError(f"FAIL: expected error={error}, got {doc.get('error')} doc={doc}")

def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="nexus-api-regress."))
    db_path = tmp / "lims.sqlite3"
    exports_dir = tmp / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["DB_PATH"] = str(db_path)

    # Setup DB (two containers to respect exclusivity)
    run(["./scripts/lims.sh", "init"], env)
    run(["./scripts/migrate.sh", "up"], env)
    run(["./scripts/lims.sh", "container", "add", "--barcode", "T1", "--kind", "tube", "--location", "bench"], env)
    run(["./scripts/lims.sh", "container", "add", "--barcode", "T2", "--kind", "tube", "--location", "bench"], env)
    run(["./scripts/lims.sh", "sample", "add", "--external-id", "S-001", "--specimen-type", "saliva", "--container", "T1"], env)
    run(["./scripts/lims.sh", "sample", "add", "--external-id", "S-002", "--specimen-type", "blood",  "--container", "T2"], env)

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
        # Wait for /health (tolerate connection refused while server boots)
        for _ in range(80):
            rc = proc.poll()
            if rc is not None:
                err = ""
                try:
                    err = (proc.stderr.read() if proc.stderr else "")
                except Exception:
                    pass
                raise RuntimeError(f"FAIL: API server exited early (rc={rc})\n{err}")

            try:
                st, h = http_json("GET", base + "/health", None)
                if st == 200 and h.get("ok") is True:
                    break
            except Exception:
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError("FAIL: API did not become healthy")

        # Negative test: missing exports_dir
        st, bad = http_json("POST", base + "/snapshot/export", {"include_samples": ["S-001"]})
        if st != 400:
            raise RuntimeError(f"FAIL: expected 400 for bad_request, got {st} doc={bad}")
        assert_api_error(st, bad, "bad_request")

        # sample report requires identifier
        st, rep = http_json("POST", base + "/sample/report", {"identifier": "S-001"})
        if st != 200 or not isinstance(rep, dict):
            raise RuntimeError(f"FAIL: /sample/report unexpected: status={st} doc={rep}")

        # Snapshot export
        st, doc = http_json("POST", base + "/snapshot/export", {
            "exports_dir": str(exports_dir),
            "include_samples": ["S-001", "S-002"],
        })
        if st != 200 or doc.get("schema") != "nexus_snapshot_export_result" or doc.get("ok") is not True:
            raise RuntimeError(f"FAIL: export json unexpected: status={st} doc={doc}")

        tarball = Path(doc["tarball"])
        if not tarball.is_file():
            raise RuntimeError(f"FAIL: tarball missing: {tarball}")

        # Snapshot verify (tarball)
        st, v = http_json("POST", base + "/snapshot/verify", {"artifact": str(tarball)})
        if st != 200 or v.get("schema") != "nexus_snapshot_verify_result" or v.get("ok") is not True:
            raise RuntimeError(f"FAIL: verify json unexpected: status={st} doc={v}")

        print("OK: API health + error schema + sample report + snapshot export/verify all work.")
        return 0

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    raise SystemExit(main())
