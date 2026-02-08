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
from urllib.parse import urlparse, parse_qs

from pathlib import Path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UI_ROOT = os.path.join(REPO_ROOT, "web")
API_EXPORTS_ROOT = os.path.join(REPO_ROOT, "exports", "api")
CLI_TIMEOUT_SEC = float(os.environ.get("NEXUS_API_CLI_TIMEOUT_SEC", "30"))

# Allow importing project modules when executed as a script.
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
try:
    from lims import db as lims_db
except Exception:
    lims_db = None

_SAMPLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_CONTAINER_BARCODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_CONTAINER_KIND_RE    = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,31}$")

def _validate_sample_id(s: str) -> str:
    v = (s or "").strip()
    if not _SAMPLE_ID_RE.match(v):
        raise ValueError("invalid sample id")
    return v


def _api_sample_add(payload: dict) -> dict:
    """
    Create a sample without spawning a subprocess (avoids CodeQL 'Uncontrolled command line').

    Input (JSON object):
      specimen_type (required)
      external_id   (optional)
      status        (optional; default 'received')
      notes         (optional)
      received_at   (optional ISO8601; default now)
      container     (optional id or barcode)

    Returns:
      {"generated_at": <iso>, "sample": {...}}
    """
    from lims import db as lims_db
    from lims.cli import ensure_db, resolve_container_id, generate_external_id, utc_now_iso
    if not isinstance(payload, dict):
        raise ValueError("body must be a JSON object")

    conn = lims_db.connect()
    ensure_db(conn)

    now = utc_now_iso()

    specimen_type = (str(payload.get("specimen_type") or "")).strip()
    if not specimen_type:
        raise ValueError("specimen_type is required")

    status_raw = (str(payload.get("status") or "received")).strip().lower()
    aliases = {"registered": "received", "testing": "processing", "analysis": "analyzing", "done": "completed"}
    status = aliases.get(status_raw, status_raw)
    allowed = {"received", "processing", "analyzing", "completed"}
    if status not in allowed:
        raise ValueError("invalid status. Allowed: received, processing, analyzing, completed")

    notes = payload.get("notes")
    notes = (str(notes).strip() if notes is not None else None) or None

    received_at = payload.get("received_at")
    received_at = (str(received_at).strip() if received_at is not None else now) or now

    provided = payload.get("external_id")
    if provided is not None:
        external_id = str(provided).strip()
        if not external_id:
            raise ValueError("external_id cannot be empty")
        if conn.execute("SELECT 1 FROM samples WHERE external_id = ? LIMIT 1", (external_id,)).fetchone():
            raise ValueError("sample external_id already exists")
    else:
        external_id = ""
        for _ in range(10):
            candidate = generate_external_id("DEV")
            if not conn.execute("SELECT 1 FROM samples WHERE external_id = ? LIMIT 1", (candidate,)).fetchone():
                external_id = candidate
                break
        if not external_id:
            raise ValueError("could not generate a unique external_id; retry")

    container_id = None
    container = payload.get("container")
    if container is not None:
        ident = str(container).strip()
        if not ident:
            raise ValueError("container cannot be empty")
        container_id = resolve_container_id(conn, ident)
        if container_id is None:
            raise ValueError("container not found")

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO samples (external_id, specimen_type, status, notes, received_at, created_at, updated_at, container_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (external_id, specimen_type, status, notes, received_at, now, now, container_id),
    )
    conn.commit()

    row = conn.execute("SELECT * FROM samples WHERE id = ?", (cur.lastrowid,)).fetchone()
    if not row:
        raise ValueError("insert succeeded but fetch failed")

    sample_obj = dict(row)
    return {"generated_at": utc_now_iso(), "sample": sample_obj}


def _clean_text_field(name: str, v, *, required: bool, max_len: int) -> str | None:
    if v is None:
        if required:
            raise ValueError(f"{name} is required")
        return None
    if not isinstance(v, str):
        raise ValueError(f"{name} must be a string")
    s = v.strip()
    if required and not s:
        raise ValueError(f"{name} is required")
    if len(s) > max_len:
        raise ValueError(f"{name} too long (max {max_len})")
    if any(c in s for c in ("\n","\r","\t")):
        raise ValueError(f"{name} contains invalid whitespace")
    return s if s else None
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


# Sample read endpoints (isolated so failures don't mask lims_db import)
try:
    from lims.api_sample_read import handle_sample_read_get
except Exception:
    def handle_sample_read_get(*args, **kwargs):
        return False


# Sample status endpoint (isolated so failures don't mask lims_db import)
try:
    from lims.api_sample_status import handle_sample_status_post
except Exception:
    def handle_sample_status_post(*args, **kwargs):
        return False

class Handler(BaseHTTPRequestHandler):
    server_version = "NexusLIMSAPI/0.3"

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

            if path in ("/app.js", "/style.css"):
                try:
                    rel = path.lstrip("/")
                    body = _read_ui_file(rel)
                    if rel.endswith(".js"):
                        ct = "application/javascript; charset=utf-8"
                    else:
                        ct = "text/css; charset=utf-8"
                    self._send_bytes(200, body, ct)
                except Exception as e:
                    msg = f"UI asset load failed: {type(e).__name__}: {e}\n".encode("utf-8")
                    self._send_bytes(500, msg, "text/plain; charset=utf-8")
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
            u = urlparse(self.path)
            path = u.path

            if handle_sample_read_get(self, path, u, lims_db):
                return

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

            if path in ("/app.js", "/style.css"):
                try:
                    rel = path.lstrip("/")
                    body = _read_ui_file(rel)
                    if rel.endswith(".js"):
                        ct = "application/javascript; charset=utf-8"
                    else:
                        ct = "text/css; charset=utf-8"
                    self._send_bytes(200, body, ct)
                except Exception as e:
                    msg = f"UI asset load failed: {type(e).__name__}: {e}\n".encode("utf-8")
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

            if path == "/metrics":
                # Prometheus-style plaintext metrics (best-effort; never raises)
                rev = _git_rev_short()
                lines = []
                lines.append('# HELP nexus_api_up API process up (always 1 if endpoint responds)')
                lines.append('# TYPE nexus_api_up gauge')
                lines.append('nexus_api_up 1')
                lines.append('# HELP nexus_build_info Build info')
                lines.append('# TYPE nexus_build_info gauge')
                lines.append('nexus_build_info{git_rev="%s"} 1' % (rev,))
                db_up = 0
                samples_total = 0
                containers_total = 0
                events_total = 0
                if lims_db is not None:
                    try:
                        conn = lims_db.connect()
                        try:
                            if hasattr(lims_db, 'apply_migrations'):
                                lims_db.apply_migrations(conn)
                            elif hasattr(lims_db, 'init_db'):
                                lims_db.init_db(conn)
                            try:
                                samples_total = int((conn.execute('SELECT COUNT(1) FROM samples').fetchone() or [0])[0] or 0)
                            except Exception:
                                samples_total = 0
                            try:
                                containers_total = int((conn.execute('SELECT COUNT(1) FROM containers').fetchone() or [0])[0] or 0)
                            except Exception:
                                containers_total = 0
                            try:
                                events_total = int((conn.execute('SELECT COUNT(1) FROM sample_events').fetchone() or [0])[0] or 0)
                            except Exception:
                                events_total = 0
                            db_up = 1
                        finally:
                            try:
                                conn.close()
                            except Exception:
                                pass
                    except Exception:
                        db_up = 0
                lines.append('# HELP nexus_db_up 1 if DB connect+query ok')
                lines.append('# TYPE nexus_db_up gauge')
                lines.append('nexus_db_up %d' % (db_up,))
                lines.append('# HELP nexus_samples_total Total samples')
                lines.append('# TYPE nexus_samples_total gauge')
                lines.append('nexus_samples_total %d' % (samples_total,))
                lines.append('# HELP nexus_containers_total Total containers')
                lines.append('# TYPE nexus_containers_total gauge')
                lines.append('nexus_containers_total %d' % (containers_total,))
                lines.append('# HELP nexus_sample_events_total Total sample events')
                lines.append('# TYPE nexus_sample_events_total gauge')
                lines.append('nexus_sample_events_total %d' % (events_total,))
                body = ('\n'.join(lines) + '\n').encode('utf-8')
                self._send_bytes(200, body, 'text/plain; version=0.0.4; charset=utf-8')
                return

            if path == "/container/list":
                if lims_db is None:
                    self._err(500, "internal_error", "lims_db import failed")
                    return
                qs = parse_qs(u.query or "")
                limit = 25
                if "limit" in qs and qs["limit"]:
                    try:
                        limit = int(str(qs["limit"][0]).strip())
                    except Exception:
                        self._err(400, "bad_request", "limit must be an int")
                        return
                if limit < 0:
                    self._err(400, "bad_request", "limit must be >= 0")
                    return
                if limit > 500:
                    limit = 500
                conn = lims_db.connect()
                try:
                    if hasattr(lims_db, "apply_migrations"):
                        lims_db.apply_migrations(conn)
                    elif hasattr(lims_db, "init_db"):
                        lims_db.init_db(conn)
                    rows = conn.execute(
                        "SELECT * FROM containers ORDER BY created_at DESC, id DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                    containers = [dict(r) for r in rows]
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass
                self._send(200, {
                    "schema": "nexus_container_list",
                    "schema_version": 1,
                    "ok": True,
                    "limit": limit,
                    "count": len(containers),
                    "containers": containers,
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

        u = urlparse(self.path)

        path = u.path

        if handle_sample_status_post(self, path, u, lims_db):

            return

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
            # POST /sample/add
            if path == "/sample/add":
                try:
                    payload = locals().get("body", None)
                    if payload is None:
                        payload = self._read_json()
                    doc = _api_sample_add(payload)
                except ValueError as ex:
                    self._err(400, "bad_request", str(ex))
                    return
                except Exception as ex:
                    self._err(500, "internal_error", "sample_add exception: %s: %s" % (type(ex).__name__, ex))
                    return
                resp = {"schema": "nexus_sample", "schema_version": 1, "ok": True}
                if isinstance(doc, dict):
                    resp.update(doc)
                else:
                    resp["sample"] = doc
                self._send(200, resp)
                return

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
            # POST /container/add
            if path == "/container/add":
                if lims_db is None:
                    self._err(500, "internal_error", "lims_db import failed")
                    return
                try:
                    barcode = _clean_text_field("barcode", body.get("barcode"), required=True, max_len=128)
                    kind = _clean_text_field("kind", body.get("kind"), required=True, max_len=64)
                    if not _CONTAINER_BARCODE_RE.match(barcode):
                        raise ValueError("invalid container barcode")
                    if not _CONTAINER_KIND_RE.match(kind):
                        raise ValueError("invalid kind")
                    location = _clean_text_field("location", body.get("location"), required=False, max_len=128)
                except ValueError as e:
                    self._err(400, "bad_request", str(e))
                    return
                conn = lims_db.connect()
                try:
                    if hasattr(lims_db, "apply_migrations"):
                        lims_db.apply_migrations(conn)
                    elif hasattr(lims_db, "init_db"):
                        lims_db.init_db(conn)
                    if conn.execute("SELECT 1 FROM containers WHERE barcode = ? LIMIT 1", (barcode,)).fetchone():
                        self._err(400, "bad_request", f"container barcode already exists: \'{barcode}\'")
                        return
                    now = lims_db.utc_now_iso() if hasattr(lims_db, "utc_now_iso") else ""
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO containers (barcode, kind, location, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                        (barcode, kind, location, now, now),
                    )
                    conn.commit()
                    cid = cur.lastrowid
                    row = conn.execute("SELECT * FROM containers WHERE id = ?", (cid,)).fetchone()
                    container = dict(row) if row else {"id": cid, "barcode": barcode, "kind": kind, "location": location}
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass
                self._send(200, {
                    "schema": "nexus_container",
                    "schema_version": 1,
                    "ok": True,
                    "container": container,
                })
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
