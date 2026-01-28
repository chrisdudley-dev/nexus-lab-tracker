#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CLI_TIMEOUT_SEC = float(os.environ.get("NEXUS_API_CLI_TIMEOUT_SEC", "30"))

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

    def do_GET(self):
        try:
            path = urlparse(self.path).path

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
                exports_dir = body.get("exports_dir")
                include_samples = body.get("include_samples", [])

                if not exports_dir or not isinstance(exports_dir, str):
                    self._err(400, "bad_request", "exports_dir must be a string")
                    return
                if not isinstance(include_samples, list) or any(not isinstance(x, str) for x in include_samples):
                    self._err(400, "bad_request", "include_samples must be a list[str]")
                    return

                cmd = ["./scripts/lims.sh", "snapshot", "export", "--exports-dir", exports_dir, "--json"]
                for sid in include_samples:
                    cmd += ["--include-sample", sid]

                rc, doc, err = _run_json(cmd, env=os.environ.copy())
                if rc == 0:
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
                cmd = ["./scripts/snapshot_verify.sh", "--json"]

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

                cmd = ["./scripts/lims.sh", "sample", "report", "--json"]
                if limit is not None:
                    cmd += ["--limit", str(limit)]
                cmd += [identifier]

                rc, doc, err = _run_json(cmd, env=os.environ.copy())
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
    args = ap.parse_args()

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
