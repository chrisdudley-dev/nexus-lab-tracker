#!/usr/bin/env python3
import json, os, socket, subprocess, tempfile, time
from pathlib import Path
from urllib.request import Request, urlopen

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

def http_json(method, url, body=None, timeout=5):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="nexus-api-regress."))
    db_path = tmp / "lims.sqlite3"
    exports_dir = tmp / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["DB_PATH"] = str(db_path)

    # Setup DB with two containers (container exclusivity enforced)
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
        # Wait for /health
        for _ in range(40):
            try:
                h = http_json("GET", base + "/health")
                if h.get("ok") is True:
                    break
            except Exception:
                time.sleep(0.1)
        else:
            # capture last stderr for debugging
            err = ""
            try:
                err = (proc.stderr.read() if proc.stderr else "")
            except Exception:
                pass
            raise RuntimeError("FAIL: API did not become healthy\n" + err)

        # Snapshot export
        doc = http_json("POST", base + "/snapshot/export", {
            "exports_dir": str(exports_dir),
            "include_samples": ["S-001", "S-002"],
        })
        if doc.get("schema") != "nexus_snapshot_export_result" or doc.get("ok") is not True:
            raise RuntimeError(f"FAIL: export json unexpected: {doc}")

        snap_dir = Path(doc["snapshot_dir"])
        tarball = Path(doc["tarball"])
        if not snap_dir.is_dir():
            raise RuntimeError(f"FAIL: snapshot_dir missing: {snap_dir}")
        if not tarball.is_file():
            raise RuntimeError(f"FAIL: tarball missing: {tarball}")

        # Snapshot verify (tarball)
        v = http_json("POST", base + "/snapshot/verify", {"artifact": str(tarball)})
        if v.get("schema") != "nexus_snapshot_verify_result" or v.get("ok") is not True:
            raise RuntimeError(f"FAIL: verify json unexpected: {v}")

        print("OK: API snapshot export + verify endpoints work.")
        return 0

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    raise SystemExit(main())
