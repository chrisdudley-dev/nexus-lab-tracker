#!/usr/bin/env python3
import os, socket, subprocess, tempfile, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

REPO_ROOT = Path(__file__).resolve().parents[1]

def run(cmd, env=None, check=True):
    p = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env or os.environ.copy(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and p.returncode != 0:
        raise SystemExit(f"FAIL cmd: {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
    return p

def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port

def http(method, url):
    req = Request(url, method=method)
    return urlopen(req, timeout=5)

def wait_health(port, tries=60):
    for _ in range(tries):
        try:
            with http("GET", f"http://127.0.0.1:{port}/health") as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(0.1)
    raise SystemExit("FAIL: API did not become healthy in time")

def main():
    tmp = Path(tempfile.mkdtemp(prefix="regress-exports-latest-"))
    db_path = tmp / "lims.sqlite3"
    exports_root = REPO_ROOT / "exports" / "api"
    exports_root.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["DB_PATH"] = str(db_path)

    # Create a fresh snapshot tarball into exports/api
    run(["./scripts/lims.sh", "init"], env=env)
    run(["./scripts/migrate.sh", "up"], env=env)
    run(["./scripts/lims.sh", "container", "add", "--barcode", "TUBE-1", "--kind", "tube", "--location", "bench-A"], env=env)
    run(["./scripts/lims.sh", "sample", "add", "--external-id", "S-001", "--specimen-type", "saliva", "--container", "TUBE-1"], env=env)
    run(["./scripts/lims.sh", "snapshot", "export", "--exports-dir", str(exports_root)], env=env)

    latest = max(exports_root.glob("*.tar.gz"), key=lambda p: p.stat().st_mtime, default=None)
    if not latest:
        raise SystemExit("FAIL: no tar.gz found in exports/api after export")

    port = free_port()
    # Start API
    api = subprocess.Popen(
        ["python3", "scripts/lims_api.py", "--port", str(port)],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_health(port)

        # HEAD should return headers and correct filename
        with http("HEAD", f"http://127.0.0.1:{port}/exports/latest") as r:
            if r.status != 200:
                raise SystemExit(f"FAIL: HEAD /exports/latest status={r.status}")
            disp = r.headers.get("Content-Disposition", "")
            if 'filename="snapshot.tar.gz"' not in disp:
                raise SystemExit(f"FAIL: Content-Disposition unexpected: {disp}")
            clen = int(r.headers.get("Content-Length", "0"))
            if clen <= 0:
                raise SystemExit("FAIL: Content-Length missing/zero on HEAD")

        # GET should return bytes (gzip stream)
        with http("GET", f"http://127.0.0.1:{port}/exports/latest") as r:
            data = r.read()
            if len(data) < 100:
                raise SystemExit(f"FAIL: GET /exports/latest too small ({len(data)} bytes)")
            if data[:2] != b"\x1f\x8b":
                raise SystemExit("FAIL: GET /exports/latest not gzip (missing 1f 8b header)")

        print("OK: /exports/latest returns latest tarball (HEAD + GET).")
    finally:
        api.terminate()
        try:
            api.wait(timeout=3)
        except Exception:
            api.kill()

if __name__ == "__main__":
    main()
