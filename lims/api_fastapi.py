from __future__ import annotations

import io
import json
import os
import subprocess
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

from fastapi import FastAPI, Request, Response
from fastapi import Response
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse

# Repo roots
REPO_ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = REPO_ROOT / "web"
API_EXPORTS_ROOT = REPO_ROOT / "exports" / "api"

try:
    from lims import db as lims_db
except Exception:
    lims_db = None

# Import existing route logic (keeps parity with stdlib server)
try:
    from lims.api_sample_read import handle_sample_read_get
except Exception:
    def handle_sample_read_get(*args, **kwargs):
        return False

try:
    from lims.api_sample_status import handle_sample_status_post
except Exception:
    def handle_sample_status_post(*args, **kwargs):
        return False


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _git_rev_short() -> str:
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(REPO_ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return p.stdout.strip() if p.returncode == 0 else ""
    except Exception:
        return ""


def _guest_ttl_seconds() -> int:
    raw = (os.environ.get("NEXUS_GUEST_TTL_SECONDS", "") or "").strip()
    try:
        v = int(raw) if raw else 12 * 60 * 60
    except Exception:
        v = 12 * 60 * 60
    if v < 60:
        v = 60
    if v > 7 * 24 * 60 * 60:
        v = 7 * 24 * 60 * 60
    return v


def _extract_session_id(headers) -> Optional[str]:
    sid = (headers.get("X-Nexus-Session") or headers.get("X-Session-Id") or "").strip()
    if not sid:
        auth = (headers.get("Authorization") or "").strip()
        if auth.lower().startswith("bearer "):
            parts = auth.split(None, 1)
            sid = parts[1].strip() if len(parts) == 2 else ""
    if not sid:
        return None
    if len(sid) > 256:
        return None
    if any(ch.isspace() for ch in sid):
        return None
    return sid


def _samples_require_auth() -> bool:
    return (os.environ.get("NEXUS_REQUIRE_AUTH_FOR_SAMPLES", "") or "").strip().lower() in ("1", "true", "yes")


def _clean_text_field(name: str, v, *, required: bool, max_len: int) -> Optional[str]:
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
    if any(c in s for c in ("\n", "\r", "\t")):
        raise ValueError(f"{name} contains invalid whitespace")
    return s if s else None


def _auth_error(status: int, error: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "schema": "nexus_api_error",
            "schema_version": 1,
            "ok": False,
            "error": error,
            "detail": detail,
        },
    )


def _require_session_request(request: Request) -> Optional[JSONResponse]:
    if lims_db is None:
        return _auth_error(500, "internal_error", "lims_db import failed")

    sid = _extract_session_id(request.headers)
    if not sid:
        return _auth_error(401, "auth_required", "missing session header (X-Nexus-Session) or Authorization: Bearer")

    conn = lims_db.connect()
    row = None
    try:
        if hasattr(lims_db, "apply_migrations"):
            lims_db.apply_migrations(conn)
        elif hasattr(lims_db, "init_db"):
            lims_db.init_db(conn)

        now = _utc_now_iso()

        # best-effort cleanup
        try:
            conn.execute("DELETE FROM guest_sessions WHERE expires_at <= ?", (now,))
            conn.commit()
        except Exception:
            pass

        row = conn.execute(
            "SELECT id FROM guest_sessions WHERE id = ? AND expires_at > ?",
            (sid, now),
        ).fetchone()

        if row:
            try:
                conn.execute("UPDATE guest_sessions SET last_seen_at = ? WHERE id = ?", (now, sid))
                conn.commit()
            except Exception:
                pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if not row:
        return _auth_error(401, "invalid_session", "session not found or expired")
    return None


def _find_latest_api_tarball() -> Optional[Path]:
    root = API_EXPORTS_ROOT.resolve()
    if not root.exists():
        return None
    best: Optional[tuple[float, Path]] = None
    for fp in root.rglob("*.tar.gz"):
        if not fp.is_file():
            continue
        try:
            m = fp.stat().st_mtime
        except OSError:
            continue
        if best is None or m > best[0]:
            best = (m, fp)
    return best[1] if best else None


def _metrics_text() -> str:
    rev = _git_rev_short()
    lines: list[str] = []
    lines.append("# HELP nexus_api_up API process up (always 1 if endpoint responds)")
    lines.append("# TYPE nexus_api_up gauge")
    lines.append("nexus_api_up 1")
    lines.append("# HELP nexus_build_info Build info")
    lines.append("# TYPE nexus_build_info gauge")
    lines.append(f'nexus_build_info{{git_rev="{rev}"}} 1')

    db_up = 0
    samples_total = 0
    containers_total = 0
    events_total = 0

    if lims_db is not None:
        try:
            conn = lims_db.connect()
            try:
                if hasattr(lims_db, "apply_migrations"):
                    lims_db.apply_migrations(conn)
                elif hasattr(lims_db, "init_db"):
                    lims_db.init_db(conn)
                try:
                    samples_total = int((conn.execute("SELECT COUNT(1) FROM samples").fetchone() or [0])[0] or 0)
                except Exception:
                    samples_total = 0
                try:
                    containers_total = int((conn.execute("SELECT COUNT(1) FROM containers").fetchone() or [0])[0] or 0)
                except Exception:
                    containers_total = 0
                try:
                    events_total = int((conn.execute("SELECT COUNT(1) FROM sample_events").fetchone() or [0])[0] or 0)
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

    lines.append("# HELP nexus_db_up 1 if DB connect+query ok")
    lines.append("# TYPE nexus_db_up gauge")
    lines.append(f"nexus_db_up {db_up}")
    lines.append("# HELP nexus_samples_total Total samples")
    lines.append("# TYPE nexus_samples_total gauge")
    lines.append(f"nexus_samples_total {samples_total}")
    lines.append("# HELP nexus_containers_total Total containers")
    lines.append("# TYPE nexus_containers_total gauge")
    lines.append(f"nexus_containers_total {containers_total}")
    lines.append("# HELP nexus_sample_events_total Total sample events")
    lines.append("# TYPE nexus_sample_events_total gauge")
    lines.append(f"nexus_sample_events_total {events_total}")
    return "\n".join(lines) + "\n"


class _Adapter:
    """Adapter object to satisfy h._send/h._err + (for POST) h.headers/h.rfile."""
    def __init__(self, headers: dict[str, str], body: bytes = b""):
        self.headers = headers
        self.rfile = io.BytesIO(body)
        self.status_code: int = 500
        self.payload: dict[str, Any] = {
            "schema": "nexus_api_error",
            "schema_version": 1,
            "ok": False,
            "error": "internal_error",
            "detail": "no response emitted",
        }

    def _send(self, code: int, obj: dict[str, Any]) -> None:
        self.status_code = int(code)
        self.payload = obj

    def _err(self, http_code: int, error: str, detail: str | None = None, **extra) -> None:
        doc: dict[str, Any] = {
            "schema": "nexus_api_error",
            "schema_version": 1,
            "ok": False,
            "error": error,
        }
        if detail is not None:
            doc["detail"] = detail
        doc.update(extra)
        self._send(int(http_code), doc)


app = FastAPI(title="Nexus LIMS API (FastAPI parity)", version="0.1")


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "schema": "nexus_api_health",
            "schema_version": 1,
            "ok": True,
            "db_path": os.environ.get("DB_PATH", ""),
            "git_rev": _git_rev_short(),
        },
    )


@app.get("/version")
async def version() -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "schema": "nexus_api_version",
            "schema_version": 1,
            "ok": True,
            "git_rev": _git_rev_short(),
        },
    )


@app.head("/metrics", include_in_schema=False)
async def metrics_head():
    # Explicit HEAD support (FastAPI may not auto-add it depending on routing)
    return Response(status_code=200, media_type="text/plain; version=0.0.4; charset=utf-8")

@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(_metrics_text(), media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/exports/latest", response_model=None)
async def exports_latest():
    fp = _find_latest_api_tarball()
    if not fp:
        return JSONResponse(status_code=404, content={"schema": "nexus_api_error", "schema_version": 1, "ok": False, "error": "not_found"})
    return FileResponse(path=str(fp), media_type="application/gzip", filename="snapshot.tar.gz")


@app.post("/auth/guest")
async def auth_guest(request: Request) -> JSONResponse:
    if lims_db is None:
        return _auth_error(500, "internal_error", "lims_db import failed")
    try:
        body = await request.json()
        if body is None:
            body = {}
        if not isinstance(body, dict):
            return _auth_error(400, "bad_request", "json body must be an object")
    except Exception:
        body = {}

    try:
        display_name = _clean_text_field("display_name", body.get("display_name"), required=False, max_len=64)
    except ValueError:
        return _auth_error(400, "bad_request", "invalid display_name")

    conn = lims_db.connect()
    try:
        if hasattr(lims_db, "apply_migrations"):
            lims_db.apply_migrations(conn)
        elif hasattr(lims_db, "init_db"):
            lims_db.init_db(conn)

        now_dt = datetime.now(timezone.utc).replace(microsecond=0)
        exp_dt = (now_dt + timedelta(seconds=_guest_ttl_seconds())).replace(microsecond=0)
        now = now_dt.isoformat()
        expires_at = exp_dt.isoformat()

        # best-effort cleanup
        try:
            conn.execute("DELETE FROM guest_sessions WHERE expires_at <= ?", (now,))
            conn.commit()
        except Exception:
            pass

        sid = secrets.token_urlsafe(24)
        conn.execute(
            "INSERT INTO guest_sessions (id, display_name, created_at, expires_at, last_seen_at) VALUES (?, ?, ?, ?, ?)",
            (sid, display_name, now, expires_at, now),
        )
        conn.commit()

        sess = {
            "id": sid,
            "display_name": display_name,
            "created_at": now,
            "expires_at": expires_at,
            "last_seen_at": now,
        }
        return JSONResponse(status_code=200, content={"schema": "nexus_auth_guest", "schema_version": 1, "ok": True, "session": sess})
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.get("/auth/me")
async def auth_me(request: Request) -> JSONResponse:
    if lims_db is None:
        return _auth_error(500, "internal_error", "lims_db import failed")

    sid = _extract_session_id(request.headers)
    if not sid:
        return _auth_error(401, "auth_required", "missing session header (X-Nexus-Session) or Authorization: Bearer")

    conn = lims_db.connect()
    row = None
    try:
        if hasattr(lims_db, "apply_migrations"):
            lims_db.apply_migrations(conn)
        elif hasattr(lims_db, "init_db"):
            lims_db.init_db(conn)

        now = _utc_now_iso()
        try:
            conn.execute("DELETE FROM guest_sessions WHERE expires_at <= ?", (now,))
            conn.commit()
        except Exception:
            pass

        row = conn.execute(
            "SELECT id, display_name, created_at, expires_at, last_seen_at FROM guest_sessions WHERE id = ? AND expires_at > ?",
            (sid, now),
        ).fetchone()

        if row:
            try:
                conn.execute("UPDATE guest_sessions SET last_seen_at = ? WHERE id = ?", (now, sid))
                conn.commit()
            except Exception:
                pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if not row:
        return _auth_error(401, "invalid_session", "session not found or expired")

    return JSONResponse(status_code=200, content={"schema": "nexus_auth_me", "schema_version": 1, "ok": True, "session": dict(row)})


# Sample read endpoints (reuse existing logic via adapter)
@app.get("/sample/list")
async def sample_list(request: Request):
    if _samples_require_auth():
        r = _require_session_request(request)
        if r is not None:
            return r
    h = _Adapter(headers=dict(request.headers))
    u = SimpleNamespace(query=str(request.url.query))
    ok = handle_sample_read_get(h, "/sample/list", u, lims_db)
    if not ok:
        return JSONResponse(status_code=404, content={"schema": "nexus_api_error", "schema_version": 1, "ok": False, "error": "not_found"})
    return JSONResponse(status_code=h.status_code, content=h.payload)


@app.get("/sample/show")
async def sample_show(request: Request):
    if _samples_require_auth():
        r = _require_session_request(request)
        if r is not None:
            return r
    h = _Adapter(headers=dict(request.headers))
    u = SimpleNamespace(query=str(request.url.query))
    ok = handle_sample_read_get(h, "/sample/show", u, lims_db)
    if not ok:
        return JSONResponse(status_code=404, content={"schema": "nexus_api_error", "schema_version": 1, "ok": False, "error": "not_found"})
    return JSONResponse(status_code=h.status_code, content=h.payload)


@app.get("/sample/events")
async def sample_events(request: Request):
    if _samples_require_auth():
        r = _require_session_request(request)
        if r is not None:
            return r
    h = _Adapter(headers=dict(request.headers))
    u = SimpleNamespace(query=str(request.url.query))
    ok = handle_sample_read_get(h, "/sample/events", u, lims_db)
    if not ok:
        return JSONResponse(status_code=404, content={"schema": "nexus_api_error", "schema_version": 1, "ok": False, "error": "not_found"})
    return JSONResponse(status_code=h.status_code, content=h.payload)


# Sample status endpoint (reuse existing logic via adapter)
@app.post("/sample/status")
async def sample_status(request: Request):
    raw = await request.body()
    hdrs = dict(request.headers)
    hdrs["Content-Length"] = str(len(raw))
    if _samples_require_auth():
        r = _require_session_request(request)
        if r is not None:
            return r
    h = _Adapter(headers=hdrs, body=raw)
    u = SimpleNamespace(query=str(request.url.query))
    ok = handle_sample_status_post(h, "/sample/status", u, lims_db)
    if not ok:
        return JSONResponse(status_code=404, content={"schema": "nexus_api_error", "schema_version": 1, "ok": False, "error": "not_found"})
    return JSONResponse(status_code=h.status_code, content=h.payload)
