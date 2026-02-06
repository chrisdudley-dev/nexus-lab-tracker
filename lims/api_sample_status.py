from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from lims.cli import ensure_db

_ALLOWED = {"received", "processing", "analyzing", "completed"}
_ALIASES = {
    "registered": "received",
    "testing": "processing",
    "analysis": "analyzing",
    "done": "completed",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json_body(h, max_bytes: int = 1024 * 1024) -> Optional[Dict[str, Any]]:
    # returns dict or None (and emits error response via h._err)
    try:
        n = int((h.headers.get("Content-Length") or "0").strip() or "0")
    except Exception:
        h._err(400, "bad_request", "invalid Content-Length")
        return None

    if n < 0:
        h._err(400, "bad_request", "invalid Content-Length")
        return None
    if n > max_bytes:
        h._err(413, "payload_too_large", f"payload too large (max {max_bytes} bytes)")
        return None

    raw = b""
    if n:
        raw = h.rfile.read(n) or b""

    if not raw:
        return {}

    try:
        obj = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        h._err(400, "bad_request", "invalid json body")
        return None

    if obj is None:
        return {}
    if not isinstance(obj, dict):
        h._err(400, "bad_request", "json body must be an object")
        return None
    return obj


def _resolve_sample_id(conn, ident: str) -> Optional[int]:
    ident = (ident or "").strip()
    if not ident:
        return None

    if ident.isdigit():
        row = conn.execute(
            "SELECT id FROM samples WHERE id = ? LIMIT 1",
            (int(ident),),
        ).fetchone()
        if row:
            return int(row[0])

    row = conn.execute(
        "SELECT id FROM samples WHERE external_id = ? LIMIT 1",
        (ident,),
    ).fetchone()
    if row:
        return int(row[0])

    return None


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return bool(row)


def _insert_sample_event(
    conn,
    sample_id: int,
    *,
    event_type: str,
    from_status: Optional[str],
    to_status: Optional[str],
    message: str,
) -> bool:
    # If sample_events doesn't exist yet, do not fail the request.
    if not _table_exists(conn, "sample_events"):
        return False

    cols = [r[1] for r in conn.execute("PRAGMA table_info(sample_events)").fetchall()]
    colset = set(cols)

    payload: Dict[str, Any] = {}

    # required-ish
    if "sample_id" in colset:
        payload["sample_id"] = sample_id
    else:
        return False

    # type name varies across schemas
    if "event_type" in colset:
        payload["event_type"] = event_type
    elif "type" in colset:
        payload["type"] = event_type

    # timestamps vary
    ts = _now_iso()
    if "occurred_at" in colset:
        payload["occurred_at"] = ts
    elif "created_at" in colset:
        payload["created_at"] = ts
    elif "timestamp" in colset:
        payload["timestamp"] = ts
    elif "ts" in colset:
        payload["ts"] = ts

    # message/note varies
    if "message" in colset:
        payload["message"] = message
    elif "note" in colset:
        payload["note"] = message
    elif "details" in colset:
        payload["details"] = message

    # status delta columns (if present)
    if "from_status" in colset and from_status is not None:
        payload["from_status"] = from_status
    if "to_status" in colset and to_status is not None:
        payload["to_status"] = to_status

    # insert using only columns that exist
    keys = [k for k in payload.keys() if k in colset]
    if not keys:
        return False

    vals = [payload[k] for k in keys]
    q = ",".join(["?"] * len(keys))
    sql = f"INSERT INTO sample_events ({', '.join(keys)}) VALUES ({q})"
    conn.execute(sql, tuple(vals))
    return True


def handle_sample_status_post(h, path: str, u: Any, lims_db) -> bool:
    # POST /sample/status
    if path != "/sample/status":
        return False

    if lims_db is None:
        h._err(500, "internal_error", "lims_db import failed")
        return True

    body = _read_json_body(h)
    if body is None:
        return True

    ident = (body.get("identifier") or body.get("external_id") or body.get("id") or "").strip()
    if not ident:
        h._err(400, "bad_request", "identifier is required")
        return True

    status_raw = (body.get("status") or "").strip().lower()
    if not status_raw:
        h._err(400, "bad_request", "status is required")
        return True

    status = _ALIASES.get(status_raw, status_raw)
    if status not in _ALLOWED:
        h._err(400, "bad_request", "invalid status. Allowed: received, processing, analyzing, completed")
        return True

    note = str(body.get("note") or body.get("message") or "").strip()
    if not note:
        note = f"status -> {status}"

    conn = lims_db.connect()
    from_status: Optional[str] = None
    event_recorded = False

    try:
        ensure_db(conn)

        sample_id = _resolve_sample_id(conn, ident)
        if sample_id is None:
            h._err(404, "not_found", "sample not found")
            return True

        prev = conn.execute(
            "SELECT status FROM samples WHERE id = ? LIMIT 1",
            (sample_id,),
        ).fetchone()
        from_status = prev[0] if prev else None

        conn.execute(
            "UPDATE samples SET status = ? WHERE id = ?",
            (status, sample_id),
        )

        try:
            event_recorded = _insert_sample_event(
                conn,
                sample_id,
                event_type="status_changed",
                from_status=(from_status if isinstance(from_status, str) else None),
                to_status=status,
                message=note,
            )
        except Exception:
            event_recorded = False

        row = conn.execute(
            "SELECT s.*, "
            "c.barcode AS container_barcode, c.kind AS container_kind, c.location AS container_location "
            "FROM samples s LEFT JOIN containers c ON s.container_id = c.id "
            "WHERE s.id = ? LIMIT 1",
            (sample_id,),
        ).fetchone()

        sample = dict(row) if row else {"id": sample_id}
        cb = sample.pop("container_barcode", None)
        ck = sample.pop("container_kind", None)
        cl = sample.pop("container_location", None)
        if sample.get("container_id") is not None and (cb is not None or ck is not None or cl is not None):
            sample["container"] = {
                "id": sample.get("container_id"),
                "barcode": cb,
                "kind": ck,
                "location": cl,
            }

        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    h._send(
        200,
        {
            "schema": "nexus_sample_status_update",
            "schema_version": 1,
            "ok": True,
            "identifier": ident,
            "from_status": from_status,
            "to_status": status,
            "event_recorded": event_recorded,
            "sample": sample,
        },
    )
    return True
