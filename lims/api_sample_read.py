from __future__ import annotations

from urllib.parse import parse_qs
from typing import Optional, Any

from lims.cli import ensure_db, resolve_container_id


def _parse_limit(h, qs, default: int, max_limit: int = 500) -> Optional[int]:
    if "limit" in qs and qs["limit"]:
        try:
            v = int(str(qs["limit"][0]).strip())
        except Exception:
            h._err(400, "bad_request", "limit must be an int")
            return None
    else:
        v = default

    if v < 0:
        h._err(400, "bad_request", "limit must be >= 0")
        return None

    return min(v, max_limit)


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


def handle_sample_read_get(h, path: str, u: Any, lims_db) -> bool:
    # GET /sample/list
    if path == "/sample/list":
        if lims_db is None:
            h._err(500, "internal_error", "lims_db import failed")
            return True

        qs = parse_qs(u.query or "")
        limit = _parse_limit(h, qs, default=25)
        if limit is None:
            return True

        status = None
        if "status" in qs and qs["status"]:
            status_raw = str(qs["status"][0]).strip().lower()
            aliases = {"registered": "received", "testing": "processing", "analysis": "analyzing", "done": "completed"}
            status = aliases.get(status_raw, status_raw)
            allowed = {"received", "processing", "analyzing", "completed"}
            if status not in allowed:
                h._err(400, "bad_request", "invalid status. Allowed: received, processing, analyzing, completed")
                return True

        container_id = None
        if "container" in qs and qs["container"]:
            ident = str(qs["container"][0]).strip()
            if not ident:
                h._err(400, "bad_request", "container cannot be empty")
                return True

            conn = lims_db.connect()
            try:
                ensure_db(conn)
                container_id = resolve_container_id(conn, ident)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

            if container_id is None:
                h._err(400, "bad_request", "container not found")
                return True

        conn = lims_db.connect()
        try:
            ensure_db(conn)

            wh = []
            params = []
            if status is not None:
                wh.append("s.status = ?")
                params.append(status)
            if container_id is not None:
                wh.append("s.container_id = ?")
                params.append(container_id)
            where = (" WHERE " + " AND ".join(wh)) if wh else ""

            sql = (
                "SELECT s.*, "
                "c.barcode AS container_barcode, c.kind AS container_kind, c.location AS container_location "
                "FROM samples s LEFT JOIN containers c ON s.container_id = c.id"
                + where +
                " ORDER BY s.received_at DESC, s.id DESC LIMIT ?"
            )
            params.append(limit)
            rows = conn.execute(sql, tuple(params)).fetchall()

            samples = []
            for r in rows:
                d = dict(r)
                cb = d.pop("container_barcode", None)
                ck = d.pop("container_kind", None)
                cl = d.pop("container_location", None)
                if d.get("container_id") is not None and (cb is not None or ck is not None or cl is not None):
                    d["container"] = {"id": d.get("container_id"), "barcode": cb, "kind": ck, "location": cl}
                samples.append(d)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        h._send(200, {
            "schema": "nexus_sample_list",
            "schema_version": 1,
            "ok": True,
            "limit": limit,
            "filters": {"status": status, "container_id": container_id},
            "count": len(samples),
            "samples": samples,
        })
        return True

    # GET /sample/show
    if path == "/sample/show":
        if lims_db is None:
            h._err(500, "internal_error", "lims_db import failed")
            return True

        qs = parse_qs(u.query or "")
        ident = None
        for k in ("identifier", "external_id", "id"):
            if k in qs and qs[k]:
                ident = str(qs[k][0]).strip()
                break

        if not ident:
            h._err(400, "bad_request", "identifier must be provided (identifier|external_id|id)")
            return True

        conn = lims_db.connect()
        try:
            ensure_db(conn)
            sample_id = _resolve_sample_id(conn, ident)
            if sample_id is None:
                h._err(404, "not_found", f"sample not found: '{ident}'")
                return True

            row = conn.execute(
                "SELECT s.*, c.barcode AS container_barcode, c.kind AS container_kind, c.location AS container_location "
                "FROM samples s LEFT JOIN containers c ON s.container_id = c.id WHERE s.id = ?",
                (sample_id,),
            ).fetchone()
            if not row:
                h._err(404, "not_found", f"sample not found: '{ident}'")
                return True

            d = dict(row)
            cb = d.pop("container_barcode", None)
            ck = d.pop("container_kind", None)
            cl = d.pop("container_location", None)
            if d.get("container_id") is not None and (cb is not None or ck is not None or cl is not None):
                d["container"] = {"id": d.get("container_id"), "barcode": cb, "kind": ck, "location": cl}
        finally:
            try:
                conn.close()
            except Exception:
                pass

        h._send(200, {"schema": "nexus_sample", "schema_version": 1, "ok": True, "sample": d})
        return True

    # GET /sample/events
    if path == "/sample/events":
        if lims_db is None:
            h._err(500, "internal_error", "lims_db import failed")
            return True

        qs = parse_qs(u.query or "")
        ident = None
        for k in ("identifier", "external_id", "id"):
            if k in qs and qs[k]:
                ident = str(qs[k][0]).strip()
                break

        if not ident:
            h._err(400, "bad_request", "identifier must be provided (identifier|external_id|id)")
            return True

        limit = _parse_limit(h, qs, default=50)
        if limit is None:
            return True

        conn = lims_db.connect()
        try:
            ensure_db(conn)
            sample_id = _resolve_sample_id(conn, ident)
            if sample_id is None:
                h._err(404, "not_found", f"sample not found: '{ident}'")
                return True

            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sample_events' LIMIT 1"
            ).fetchone()

            events = []
            if exists:
                cols = [r[1] for r in conn.execute("PRAGMA table_info(sample_events)").fetchall()]
                if "occurred_at" in cols:
                    order = "occurred_at ASC, id ASC"
                elif "created_at" in cols:
                    order = "created_at ASC, id ASC"
                else:
                    order = "id ASC"

                rows = conn.execute(
                    f"SELECT * FROM sample_events WHERE sample_id = ? ORDER BY {order} LIMIT ?",
                    (sample_id, limit),
                ).fetchall()
                events = [dict(r) for r in rows]
        finally:
            try:
                conn.close()
            except Exception:
                pass

        h._send(200, {
            "schema": "nexus_sample_events",
            "schema_version": 1,
            "ok": True,
            "identifier": ident,
            "sample_id": sample_id,
            "limit": limit,
            "count": len(events),
            "events": events,
        })
        return True

    return False
