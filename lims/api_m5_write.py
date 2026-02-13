from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

try:
    from lims import db as lims_db
except Exception:
    lims_db = None

router = APIRouter()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _api_error(status: int, error: str, detail: str, **extra) -> JSONResponse:
    doc: dict[str, Any] = {
        "schema": "nexus_api_error",
        "schema_version": 1,
        "ok": False,
        "error": error,
        "detail": detail,
    }
    doc.update(extra)
    return JSONResponse(status_code=int(status), content=doc)


def _db_init(conn) -> None:
    if lims_db is None:
        return
    if hasattr(lims_db, "apply_migrations"):
        lims_db.apply_migrations(conn)
    elif hasattr(lims_db, "init_db"):
        lims_db.init_db(conn)


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return bool(row)


def _clean_text(v: Any, *, field: str, required: bool, max_len: int) -> Optional[str]:
    if v is None:
        if required:
            raise ValueError(f"{field} is required")
        return None
    if not isinstance(v, str):
        raise ValueError(f"{field} must be a string")
    s = v.strip()
    if required and not s:
        raise ValueError(f"{field} is required")
    if len(s) > max_len:
        raise ValueError(f"{field} too long (max {max_len})")
    if any(c in s for c in ("\n", "\r", "\t")):
        raise ValueError(f"{field} contains invalid whitespace")
    return s if s else None


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


def _require_auth_for_writes() -> bool:
    return (os.environ.get("NEXUS_REQUIRE_AUTH_FOR_WRITES", "") or "").strip().lower() in ("1", "true", "yes")


def _require_session(headers) -> Optional[JSONResponse]:
    if not _require_auth_for_writes():
        return None
    if lims_db is None:
        return _api_error(500, "internal_error", "lims_db import failed")

    sid = _extract_session_id(headers)
    if not sid:
        return _api_error(401, "auth_required", "missing session header (X-Nexus-Session) or Authorization: Bearer")

    conn = lims_db.connect()
    try:
        _db_init(conn)
        now = _utc_now_iso()

        try:
            conn.execute("DELETE FROM guest_sessions WHERE expires_at <= ?", (now,))
            conn.commit()
        except Exception:
            pass

        row = conn.execute(
            "SELECT id FROM guest_sessions WHERE id = ? AND expires_at > ?",
            (sid, now),
        ).fetchone()
        if not row:
            return _api_error(401, "invalid_session", "session not found or expired")

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

    return None


def _resolve_container_id(conn, ident: str) -> Optional[int]:
    ident = (ident or "").strip()
    if not ident:
        return None
    if ident.isdigit():
        row = conn.execute("SELECT id FROM containers WHERE id = ? LIMIT 1", (int(ident),)).fetchone()
        if row:
            return int(row[0])
    row = conn.execute("SELECT id FROM containers WHERE barcode = ? LIMIT 1", (ident,)).fetchone()
    if row:
        return int(row[0])
    return None


def _resolve_sample_id(conn, ident: str) -> Optional[int]:
    ident = (ident or "").strip()
    if not ident:
        return None
    if ident.isdigit():
        row = conn.execute("SELECT id FROM samples WHERE id = ? LIMIT 1", (int(ident),)).fetchone()
        if row:
            return int(row[0])
    row = conn.execute("SELECT id FROM samples WHERE external_id = ? LIMIT 1", (ident,)).fetchone()
    if row:
        return int(row[0])
    return None


def _normalize_status(v: Any) -> tuple[str, Optional[JSONResponse]]:
    if v is None:
        return "received", None
    if not isinstance(v, str):
        return "received", _api_error(400, "bad_request", "status must be a string")
    s = v.strip().lower()
    if not s:
        return "received", None
    aliases = {"registered": "received", "testing": "processing", "analysis": "analyzing", "done": "completed"}
    s = aliases.get(s, s)
    allowed = {"received", "processing", "analyzing", "completed"}
    if s not in allowed:
        return "received", _api_error(400, "bad_request", "invalid status. Allowed: received, processing, analyzing, completed")
    return s, None


def _insert_event(conn, *, sample_id: int, event_type: str, note: str | None = None, occurred_at: str | None = None) -> bool:
    try:
        if not _table_exists(conn, "sample_events"):
            return False
        ts = _utc_now_iso()
        oa = (occurred_at or ts).strip()
        conn.execute(
            "INSERT INTO sample_events (sample_id, event_type, note, occurred_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (sample_id, event_type, (note or None), oa, ts),
        )
        return True
    except Exception:
        return False


@router.post("/container/add")
async def container_add(request: Request) -> JSONResponse:
    r = _require_session(request.headers)
    if r is not None:
        return r
    if lims_db is None:
        return _api_error(500, "internal_error", "lims_db import failed")

    try:
        body = await request.json()
        if body is None:
            body = {}
        if not isinstance(body, dict):
            return _api_error(400, "bad_request", "json body must be an object")
    except Exception:
        body = {}

    try:
        barcode = _clean_text(body.get("barcode"), field="barcode", required=True, max_len=64)
        kind = _clean_text(body.get("kind"), field="kind", required=True, max_len=32)
        location = _clean_text(body.get("location"), field="location", required=False, max_len=128)
    except ValueError as e:
        return _api_error(400, "bad_request", str(e))

    is_exclusive_raw = body.get("is_exclusive", 0)
    is_exclusive = 1 if str(is_exclusive_raw).strip().lower() in ("1", "true", "yes", "on") else 0

    conn = lims_db.connect()
    try:
        _db_init(conn)
        if not _table_exists(conn, "containers"):
            return _api_error(500, "internal_error", "containers table missing")

        row = conn.execute("SELECT id FROM containers WHERE barcode = ? LIMIT 1", (barcode,)).fetchone()
        if row:
            return _api_error(409, "already_exists", "container barcode already exists", id=int(row[0]))

        now = _utc_now_iso()
        conn.execute(
            "INSERT INTO containers (barcode, kind, location, created_at, updated_at, is_exclusive) VALUES (?, ?, ?, ?, ?, ?)",
            (barcode, kind, location, now, now, is_exclusive),
        )
        cid = int((conn.execute("SELECT last_insert_rowid()").fetchone() or [0])[0] or 0)
        conn.commit()

        row = conn.execute("SELECT * FROM containers WHERE id = ? LIMIT 1", (cid,)).fetchone()
        return JSONResponse(status_code=200, content={"schema": "nexus_container", "schema_version": 1, "ok": True, "container": dict(row) if row else {"id": cid}})
    finally:
        try:
            conn.close()
        except Exception:
            pass


@router.get("/container/list")
async def container_list(request: Request) -> JSONResponse:
    if lims_db is None:
        return _api_error(500, "internal_error", "lims_db import failed")

    qs = parse_qs(str(request.url.query or ""))
    try:
        limit = int(str(qs.get("limit", ["25"])[0]).strip())
    except Exception:
        return _api_error(400, "bad_request", "limit must be an int")
    if limit < 0:
        return _api_error(400, "bad_request", "limit must be >= 0")
    limit = min(limit, 500)

    conn = lims_db.connect()
    try:
        _db_init(conn)
        if not _table_exists(conn, "containers"):
            return _api_error(500, "internal_error", "containers table missing")
        rows = conn.execute("SELECT * FROM containers ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        containers = [dict(r) for r in rows]
        return JSONResponse(status_code=200, content={"schema": "nexus_container_list", "schema_version": 1, "ok": True, "limit": limit, "count": len(containers), "containers": containers})
    finally:
        try:
            conn.close()
        except Exception:
            pass


@router.get("/container/show")
async def container_show(request: Request) -> JSONResponse:
    if lims_db is None:
        return _api_error(500, "internal_error", "lims_db import failed")

    qs = parse_qs(str(request.url.query or ""))
    ident = None
    for k in ("identifier", "barcode", "id"):
        if k in qs and qs[k]:
            ident = str(qs[k][0]).strip()
            break
    if not ident:
        return _api_error(400, "bad_request", "identifier must be provided (identifier|barcode|id)")

    conn = lims_db.connect()
    try:
        _db_init(conn)
        cid = _resolve_container_id(conn, ident)
        if cid is None:
            return _api_error(404, "not_found", f"container not found: '{ident}'")
        row = conn.execute("SELECT * FROM containers WHERE id = ? LIMIT 1", (cid,)).fetchone()
        if not row:
            return _api_error(404, "not_found", f"container not found: '{ident}'")
        return JSONResponse(status_code=200, content={"schema": "nexus_container", "schema_version": 1, "ok": True, "container": dict(row)})
    finally:
        try:
            conn.close()
        except Exception:
            pass


@router.post("/sample/add")
async def sample_add(request: Request) -> JSONResponse:
    r = _require_session(request.headers)
    if r is not None:
        return r
    if lims_db is None:
        return _api_error(500, "internal_error", "lims_db import failed")

    try:
        body = await request.json()
        if body is None:
            body = {}
        if not isinstance(body, dict):
            return _api_error(400, "bad_request", "json body must be an object")
    except Exception:
        body = {}

    try:
        specimen_type = _clean_text(body.get("specimen_type"), field="specimen_type", required=True, max_len=64)
        external_id = _clean_text(body.get("external_id"), field="external_id", required=False, max_len=64)
        notes = _clean_text(body.get("notes"), field="notes", required=False, max_len=2000)
        received_at = _clean_text(body.get("received_at"), field="received_at", required=False, max_len=64)
    except ValueError as e:
        return _api_error(400, "bad_request", str(e))

    status, err = _normalize_status(body.get("status"))
    if err is not None:
        return err

    container_ident = None
    for k in ("container", "container_barcode", "container_id"):
        v = body.get(k)
        if v is not None and str(v).strip():
            container_ident = str(v).strip()
            break

    conn = lims_db.connect()
    try:
        _db_init(conn)
        if not _table_exists(conn, "samples"):
            return _api_error(500, "internal_error", "samples table missing")

        container_id = None
        if container_ident is not None:
            if not _table_exists(conn, "containers"):
                return _api_error(400, "bad_request", "containers table missing; cannot link container")
            container_id = _resolve_container_id(conn, container_ident)
            if container_id is None:
                return _api_error(400, "bad_request", "container not found")

        if not external_id:
            external_id = f"AUTO-{secrets.token_urlsafe(8)}"
        else:
            row = conn.execute("SELECT id FROM samples WHERE external_id = ? LIMIT 1", (external_id,)).fetchone()
            if row:
                return _api_error(409, "already_exists", "sample external_id already exists", id=int(row[0]))

        now = _utc_now_iso()
        ra = received_at or now

        conn.execute(
            "INSERT INTO samples (external_id, specimen_type, status, notes, received_at, created_at, updated_at, container_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (external_id, specimen_type, status, notes, ra, now, now, container_id),
        )
        sid = int((conn.execute("SELECT last_insert_rowid()").fetchone() or [0])[0] or 0)

        event_recorded = _insert_event(conn, sample_id=sid, event_type="created", note=notes, occurred_at=ra)
        conn.commit()

        row = conn.execute("SELECT * FROM samples WHERE id = ? LIMIT 1", (sid,)).fetchone()
        return JSONResponse(status_code=200, content={"schema": "nexus_sample_create", "schema_version": 1, "ok": True, "event_recorded": bool(event_recorded), "sample": dict(row) if row else {"id": sid}})
    finally:
        try:
            conn.close()
        except Exception:
            pass


@router.post("/sample/event")
async def sample_event(request: Request) -> JSONResponse:
    r = _require_session(request.headers)
    if r is not None:
        return r
    if lims_db is None:
        return _api_error(500, "internal_error", "lims_db import failed")

    try:
        body = await request.json()
        if body is None:
            body = {}
        if not isinstance(body, dict):
            return _api_error(400, "bad_request", "json body must be an object")
    except Exception:
        body = {}

    ident = str(body.get("identifier") or body.get("external_id") or body.get("id") or "").strip()
    if not ident:
        return _api_error(400, "bad_request", "identifier is required")

    try:
        event_type = _clean_text(body.get("event_type"), field="event_type", required=True, max_len=64)
        note = _clean_text(body.get("note") or body.get("message"), field="note", required=False, max_len=2000)
        occurred_at = _clean_text(body.get("occurred_at"), field="occurred_at", required=False, max_len=64)
    except ValueError as e:
        return _api_error(400, "bad_request", str(e))

    conn = lims_db.connect()
    try:
        _db_init(conn)
        sid = _resolve_sample_id(conn, ident)
        if sid is None:
            return _api_error(404, "not_found", "sample not found")
        ok = _insert_event(conn, sample_id=sid, event_type=event_type, note=note, occurred_at=occurred_at)
        conn.commit()
        return JSONResponse(status_code=200, content={"schema": "nexus_sample_event_append", "schema_version": 1, "ok": True, "identifier": ident, "sample_id": sid, "event_recorded": bool(ok)})
    finally:
        try:
            conn.close()
        except Exception:
            pass
