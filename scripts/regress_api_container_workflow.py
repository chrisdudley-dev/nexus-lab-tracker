#!/usr/bin/env python3
import json, os, socket, subprocess, tempfile, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

REPO_ROOT = Path(__file__).resolve().parents[1]

def run_api(env):
    # choose a free local port
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    cmd = ["python3", "scripts/lims_api.py", "--host", "127.0.0.1", "--port", str(port)]
    p = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return p, port

def http_json(method, url, body=None):
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=10) as r:
            raw = r.read()
            ct = (r.headers.get("content-type") or "").lower()
            if "application/json" in ct:
                return r.status, json.loads(raw.decode("utf-8", errors="replace"))
            return r.status, raw.decode("utf-8", errors="replace")
    except HTTPError as e:
        raw = e.read()
        try:
            j = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            j = {"raw": raw.decode("utf-8", errors="replace")}
        return e.code, j

def wait_health(port, tries=60, sleep_s=0.10):
    url = f"http://127.0.0.1:{port}/health"
    last = None
    for _ in range(tries):
        try:
            st, j = http_json("GET", url)
            if st == 200 and isinstance(j, dict) and j.get("ok") is True:
                return
            last = (st, j)
        except Exception as e:
            last = ("exc", repr(e))
        time.sleep(sleep_s)
    raise RuntimeError(f"API did not become healthy. last={last}")

def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)

def main():
    tmp = tempfile.TemporaryDirectory()
    db_path = str(Path(tmp.name) / "lims.sqlite3")

    env = os.environ.copy()
    env["DB_PATH"] = db_path
    # ensure API ignores these (we unset anyway when starting)
    env.pop("EXPORT_DIR", None)
    env.pop("EXPORTS_DIR", None)

    p, port = run_api(env)
    try:
        wait_health(port)

        base = f"http://127.0.0.1:{port}"

        # add container
        barcode = f"REG-TUBE-{int(time.time())}"
        st, j = http_json("POST", base + "/container/add", {
            "barcode": barcode,
            "kind": "tube",
            "location": "bench-A",
        })
        assert_true(st == 200, f"add expected 200 got {st} {j}")
        assert_true(j.get("ok") is True and j.get("schema") == "nexus_container", f"bad add resp: {j}")

        # duplicate should 400
        st, j2 = http_json("POST", base + "/container/add", {
            "barcode": barcode,
            "kind": "tube",
            "location": "bench-A",
        })
        assert_true(st == 400, f"dup expected 400 got {st} {j2}")
        assert_true(j2.get("ok") is False and j2.get("schema") == "nexus_api_error", f"bad dup resp: {j2}")

        # traversal should 400
        st, j3 = http_json("POST", base + "/container/add", {
            "barcode": "../../etc/passwd",
            "kind": "tube",
            "location": "bench-A",
        })
        assert_true(st == 400, f"traversal expected 400 got {st} {j3}")
        assert_true("invalid container barcode" in str(j3.get("detail", "")).lower(), f"unexpected traversal detail: {j3}")

        # list should include
        st, j4 = http_json("GET", base + "/container/list?limit=50")
        assert_true(st == 200, f"list expected 200 got {st} {j4}")
        assert_true(j4.get("ok") is True and j4.get("schema") == "nexus_container_list", f"bad list resp: {j4}")
        found = any(isinstance(c, dict) and c.get("barcode") == barcode for c in (j4.get("containers") or []))
        assert_true(found, f"expected barcode {barcode} in list; got {j4.get('containers')}")

        print("OK: API container workflow (add/list + dup + traversal)")

    finally:
        try:
            p.terminate()
            p.wait(timeout=3)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
        tmp.cleanup()

if __name__ == "__main__":
    main()
