#!/usr/bin/env python3
import argparse
import json
import re
import os
import tempfile
import subprocess
import sys
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from pathlib import Path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UI_ROOT = os.path.join(REPO_ROOT, "web")
API_EXPORTS_ROOT = os.path.join(REPO_ROOT, "exports", "api")
CLI_TIMEOUT_SEC = float(os.environ.get("NEXUS_API_CLI_TIMEOUT_SEC", "30"))

_SAMPLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")

def _validate_sample_id(s: str) -> str:
    v = (s or "").strip()
    if not _SAMPLE_ID_RE.match(v):
        raise ValueError("invalid sample id")
    return v

def _mk_api_exports_dir() -> str:
    # Force exports under repo-controlled directory; never trust a client path.
    base = os.path.join(REPO_ROOT, "exports", "api")
    os.makedirs(base, exist_ok=True)
    return tempfile.mkdtemp(prefix="snapshot-", dir=base)


def _find_latest_api_tarball() -> str | None:
    """Return filesystem path to the most recent API-created snapshot tarball."""
    root = Path(API_EXPORTS_ROOT).resolve()
    if not root.exists():
        return None
    best = None
    for fp in root.rglob("*.tar.gz"):
        if not fp.is_file():
            continue
        try:
            m = fp.stat().st_mtime
        except OSError:
            continue
        if best is None or m > best[0]:
            best = (m, fp)
    return str(best[1]) if best else None

def _read_ui_file(rel_path: str) -> bytes:
    """
    Read a UI file from UI_ROOT safely (blocks path traversal).
    """
    base = Path(UI_ROOT).resolve()
    p = (base / rel_path).resolve()
    if p != base and base not in p.parents:
        raise ValueError("invalid ui path")
    return p.read_bytes()


def _exports_safe_path(filename: str) -> Path:
    """Resolve an export artifact by filename under <REPO_ROOT>/exports/api.

    Layout today:
      exports/api/snapshot-<rand>/<filename>
    """
    # Only allow a simple filename (no slashes / traversal).
    if not filename or filename.strip() != filename:
        raise ValueError("invalid filename")
    if "/" in filename or "\\" in filename:
        raise ValueError("invalid filename")

    base = Path(REPO_ROOT).joinpath("exports", "api").resolve()

    # Direct child (rare but harmless to support)
    direct = (base / filename)
    if direct.is_file():
        return direct.resolve()

    # Common case: exports/api/snapshot-<rand>/<filename>
    if base.is_dir():
        for d in base.iterdir():
            if d.is_dir() and d.name.startswith("snapshot-"):
                cand = (d / filename)
                if cand.is_file():
                    return cand.resolve()

    raise FileNotFoundError("artifact not found")

def _is_loopback(host: str) -> bool:
    h = (host or "").strip().lower()
    return h in ("127.0.0.1", "localhost", "::1") or h.startswith("127.")


def _run_json(cmd, env=None, timeout_sec=None):
    timeout = CLI_TIMEOUT_SEC if timeout_sec is None else float(timeout_sec)
    try:
        p = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired as e:
        return (124, None, f"timeout after {timeout:.1f}s: {cmd}\n{e}")

    out = p.stdout.strip()
    if p.returncode != 0:
        return (p.returncode, None, p.stderr)

    try:
        return (0, json.loads(out) if out else {}, p.stderr)
    except Exception as e:
        return (2, None, f"stdout was not valid JSON: {e}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")

def _git_rev_short():
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            check=False,
        )
        return p.stdout.strip() if p.returncode == 0 else ""
    except Exception:
        return ""

class Handler(BaseHTTPRequestHandler):
    server_version = "NexusLIMSAPI/0.2"

    def _send(self, code, obj):
        body = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def _send_bytes(self, code: int, body: bytes, content_type: str):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


    def _err(self, http_code, error, detail=None, **extra):
        doc = {
            "schema": "nexus_api_error",
            "schema_version": 1,
            "ok": False,
            "error": error,
        }
        if detail is not None:
            doc["detail"] = detail
        doc.update(extra)
        self._send(http_code, doc)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(n) if n > 0 else b""
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"invalid JSON body: {e}")

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))
    def do_HEAD(self):
        try:
            path = urlparse(self.path).path
            if path == "/exports/latest":
                latest = _find_latest_api_tarball()
                if not latest:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                fp = Path(latest)
                try:
                    st = fp.stat()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/gzip")
                    self.send_header("Content-Length", str(st.st_size))
                    self.send_header("Content-Disposition", 'attachment; filename="snapshot.tar.gz"')
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                except Exception:
                    self.send_response(500)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                return


            if path.startswith("/exports/") and path != "/exports/latest":
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            # Mirror the GET routes we care about, but send headers only.
            if path in ("/", "/index.html", "/ui"):
                try:
                    body = _read_ui_file("index.html")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                except Exception as e:
                    msg = f"UI load failed: {type(e).__name__}: {e}\\n".encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(msg)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                return

            if path == "/health":
                body = json.dumps(
                    {"schema": "nexus_api_health", "ok": True},
                    sort_keys=True,
                    separators=(",", ":")
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return

            # Default: HEAD not supported for other paths
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

        except Exception:
            self.send_response(500)
            self.send_header("Content-Length", "0")
            self.end_headers()



    def do_GET(self):
        try:
            path = urlparse(self.path).path

            # Download export artifacts (server-controlled dir only).
            if path == "/exports/latest":
                latest = _find_latest_api_tarball()
                if not latest:
                    self._err(404, "not_found", path=path, method="GET")
                    return
                fp = Path(latest)
                try:
                    st = fp.stat()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/gzip")
                    self.send_header("Content-Length", str(st.st_size))
                    self.send_header("Content-Disposition", 'attachment; filename="snapshot.tar.gz"')
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    with fp.open("rb") as f:
                        while True:
                            chunk = f.read(1024 * 1024)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                except Exception as e:
                    msg = f"download failed: {type(e).__name__}: {e}\n".encode("utf-8")
                    self._send_bytes(500, msg, "text/plain; charset=utf-8")
                return

            if path.startswith("/exports/") and path != "/exports/latest":
                self._err(404, "not_found", path=path, method="GET")
                return
            if path in ("/", "/index.html", "/ui"):
                try:
                    body = _read_ui_file("index.html")
                    self._send_bytes(200, body, "text/html; charset=utf-8")
                except Exception as e:
                    msg = f"UI load failed: {type(e).__name__}: {e}\n".encode("utf-8")
                    self._send_bytes(500, msg, "text/plain; charset=utf-8")
                return

            if path == "/health":
                self._send(200, {
                    "schema": "nexus_api_health",
                    "schema_version": 1,
                    "ok": True,
                    "db_path": os.environ.get("DB_PATH", ""),
                    "git_rev": _git_rev_short(),
                })
                return

            if path == "/version":
                self._send(200, {
                    "schema": "nexus_api_version",
                    "schema_version": 1,
                    "ok": True,
                    "git_rev": _git_rev_short(),
                })
                return

            self._err(404, "not_found", path=path, method="GET")
        except Exception as e:
            detail = "%s exception: %s: %s" % ("do_GET", type(e).__name__, e)
            try:
                self._err(500, "internal_error", detail)
            except Exception:
                pass

    def do_POST(self):
        try:
            path = urlparse(self.path).path

            try:
                body = self._read_json()
            except ValueError as e:
                self._err(400, "bad_request", str(e))
                return

            # POST /snapshot/export
            if path == "/snapshot/export":
                                                    _ = body.get("exports_dir")  # ignored; server chooses a safe dir
                                                    include_samples = body.get("include_samples", [])

                                                    if include_samples is None:
                                                        include_samples = []
                                                    if not isinstance(include_samples, list) or any(not isinstance(x, str) for x in include_samples):
                                                        self._err(400, "bad_request", "include_samples must be a list[str]")
                                                        return

                                                    # Always write exports to a safe server-side directory (prevents path abuse).
                                                    exports_dir = _mk_api_exports_dir()
                                                    env = os.environ.copy()
                                                    env["EXPORTS_DIR"] = exports_dir
                                                    if include_samples:
                                                        try:
                                                            cleaned = [_validate_sample_id(x) for x in include_samples]
                                                        except ValueError as e:
                                                            self._err(400, "bad_request", str(e))
                                                            return
                                                        # Pass via env var to avoid user input on the subprocess command line.
                                                        env["NEXUS_API_INCLUDE_SAMPLES"] = "\n".join(cleaned)

                                                    cmd = ["./scripts/lims.sh", "snapshot", "export", "--json"]
                                                    rc, doc, err = _run_json(cmd, env=env)
                                                    if rc == 0:
                                                        # Make exports_dir explicit in the response for clients.
                                                        if isinstance(doc, dict):
                                                            doc.setdefault("exports_dir", exports_dir)
                                                        self._send(200, doc)
                                                    elif rc == 124:
                                                        self._err(504, "command_timeout", rc=rc, stderr=err)
                                                    else:
                                                        self._err(400, "command_failed", rc=rc, stderr=err)
                                                    return

            # POST /snapshot/verify
            if path == "/snapshot/verify":
                artifact = body.get("artifact")
                if not artifact or not isinstance(artifact, str):
                    self._err(400, "bad_request", "artifact must be a string")
                    return

                env = os.environ.copy()
                env["SNAPSHOT_ARTIFACT"] = artifact
                cmd = ["bash", "./scripts/snapshot_verify.sh", "--json"]

                rc, doc, err = _run_json(cmd, env=env)
                if rc == 0:
                    self._send(200, doc)
                elif rc == 124:
                    self._err(504, "command_timeout", rc=rc, stderr=err)
                else:
                    self._err(400, "command_failed", rc=rc, stderr=err)
                return

            # POST /sample/report
            if path == "/sample/report":
                identifier = body.get("identifier", None)
                if not identifier or not isinstance(identifier, str):
                    self._err(400, "bad_request", "identifier must be a string")
                    return

                limit = body.get("limit", None)
                if limit is not None:
                    if not isinstance(limit, int) or limit < 0:
                        self._err(400, "bad_request", "limit must be a non-negative int")
                        return

                env = os.environ.copy()
                env["NEXUS_API_SAMPLE_IDENTIFIER"] = identifier
                if limit is not None:
                    env["NEXUS_API_SAMPLE_REPORT_LIMIT"] = str(limit)

                cmd = ["./scripts/lims.sh", "sample", "report", "--json"]
                rc, doc, err = _run_json(cmd, env=env)

                if rc == 0:
                    self._send(200, doc)
                elif rc == 124:
                    self._err(504, "command_timeout", rc=rc, stderr=err)
                else:
                    self._err(400, "command_failed", rc=rc, stderr=err)
                return

            self._err(404, "not_found", path=path, method="POST")
        except Exception as e:
            detail = "%s exception: %s: %s" % ("do_POST", type(e).__name__, e)
            try:
                self._err(500, "internal_error", detail)
            except Exception:
                pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--allow-remote", action="store_true", help="Allow binding to non-loopback interfaces")
    args = ap.parse_args()

    if not _is_loopback(args.host) and not args.allow_remote:
        sys.stderr.write(f"ERROR: refusing to bind to {args.host}. Use --allow-remote if you intend remote access.\n")
        sys.exit(2)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    httpd.daemon_threads = True
    sys.stderr.write(f"OK: Nexus LIMS API listening on http://{args.host}:{args.port}\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("OK: shutting down (Ctrl+C)\n")
    finally:
        httpd.server_close()

if __name__ == "__main__":
    main()
