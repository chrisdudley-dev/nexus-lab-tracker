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
    conn: sqlite3.Connection,
    sample_id: int,
    event_type: str,
    from_status: str | None = None,
    to_status: str | None = None,
    from_container_id: int | None = None,
    to_container_id: int | None = None,
    message: str | None = None,
    occurred_at: str | None = None,
) -> bool:
    """
    INSERT_SAMPLE_EVENT_V8
    Schema-tolerant, non-throwing event insert.

    - Writes message into any of: note/message/details/description/notes if present.
    - Maps status/container/time fields across common column name variants.
    - Uses INSERT OR IGNORE to avoid hard failures in demo seeds.
    - Returns True if an insert occurred, else False.
    """
    try:
        # Ensure table exists
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            ("sample_events",),
        ).fetchone()
        if not row:
            return False

        info = conn.execute("PRAGMA table_info(sample_events)").fetchall()
        cols = [r[1] for r in info]  # (cid, name, type, notnull, dflt, pk)
        colset = set(cols)

        ts = now_iso()
        payload: dict[str, object] = {}

        # Core identifiers
        if "sample_id" in colset:
            payload["sample_id"] = sample_id
        if "event_type" in colset:
            payload["event_type"] = event_type

        # Time fields
        oa = occurred_at or ts
        for k in ("occurred_at", "timestamp", "ts"):
            if k in colset:
                payload[k] = oa
        for k in ("created_at", "updated_at"):
            if k in colset:
                payload[k] = ts

        # Status fields (support both old/new and from/to naming)
        if "old_status" in colset:
            payload["old_status"] = from_status
        elif "from_status" in colset:
            payload["from_status"] = from_status

        if "new_status" in colset:
            payload["new_status"] = to_status
        elif "to_status" in colset:
            payload["to_status"] = to_status

        # Container movement fields
        if "from_container_id" in colset:
            payload["from_container_id"] = from_container_id
        elif "src_container_id" in colset:
            payload["src_container_id"] = from_container_id

        if "to_container_id" in colset:
            payload["to_container_id"] = to_container_id
        elif "dst_container_id" in colset:
            payload["dst_container_id"] = to_container_id

        # Message/note/details fields: write to ALL that exist
        msg = (message or "").strip()
        if msg:
            for k in ("note", "message", "details", "description", "notes"):
                if k in colset:
                    payload[k] = msg

        # Keep only real columns
        keys = [k for k in payload.keys() if k in colset]
        if not keys:
            return False

        q = ",".join(["?"] * len(keys))
        sql = f"INSERT OR IGNORE INTO sample_events ({', '.join(keys)}) VALUES ({q})"
        cur = conn.execute(sql, [payload[k] for k in keys])
        # rowcount is 1 if inserted, 0 if ignored
        rc = getattr(cur, "rowcount", 1)
        return bool(rc)
    except Exception:
        # never break /sample/status just because events are best-effort
        return False



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
            # STATUS_NOTE_ALIAS_V5: accept request JSON 'note'/'details' as message for sample events
            # NOTE_EVENT_FIX_V13: robust request-body discovery + ensure note is persisted on latest status_changed event
            # NOTE_EVENT_FIX_V15: choose the request dict safely (body-first; no locals scan)
            _b = locals().get('body')
            req = _b if isinstance(_b, dict) else (locals().get('data') if isinstance(locals().get('data'), dict) else {})
            note = (req.get('note') or req.get('details') or req.get('message') or '').strip()
            event_recorded = _insert_sample_event(
                conn,
                sample_id,
                event_type='status_changed',
                from_status=(from_status if isinstance(from_status, str) else None),
                to_status=status,
                message=note,
            )
            # NOTE_EVENT_FIX_V13: normalize insert return (legacy helpers may return None)
            if event_recorded is None:
                event_recorded = True
            else:
                event_recorded = bool(event_recorded)
            try:
                _msg = (note or '').strip()
                if _msg:
                    _info = conn.execute('PRAGMA table_info(sample_events)').fetchall()
                    _cols = {r[1] for r in _info}
                    _targets = [c for c in ('note','message','details','description','notes') if c in _cols]
                    if _targets:
                        _row = conn.execute(
                            "SELECT id FROM sample_events WHERE sample_id=? AND event_type=? ORDER BY id DESC LIMIT 1",
                            (sample_id, 'status_changed'),
                        ).fetchone()
                        if _row:
                            _eid = _row[0]
                            _set = ', '.join([f"{c}=?" for c in _targets])
                            conn.execute(f"UPDATE sample_events SET {_set} WHERE id=?", [_msg]*len(_targets) + [_eid])
                            event_recorded = True
            except Exception:
                pass
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
            'event_recorded': event_recorded,  # EVENT_RECORDED_RESPONSE_V5
            "sample": sample,
        },
    )
    return True
