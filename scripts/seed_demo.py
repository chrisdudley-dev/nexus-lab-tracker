#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import sys
# Allow running as: python3 scripts/seed_demo.py (imports from repo root)
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from lims.cli import ensure_db
except Exception as e:
    raise SystemExit(f"ERROR: cannot import lims.cli.ensure_db: {e}")

STATUSES = ["received", "processing", "analyzing", "completed"]

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return bool(row)

def table_cols(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}

def insert_or_ignore(conn: sqlite3.Connection, table: str, payload: dict) -> None:
    cols = table_cols(conn, table)
    data = {k: v for k, v in payload.items() if k in cols}
    if not data:
        return
    keys = list(data.keys())
    q = ",".join(["?"] * len(keys))
    sql = f"INSERT OR IGNORE INTO {table} ({', '.join(keys)}) VALUES ({q})"
    conn.execute(sql, [data[k] for k in keys])

def get_id(conn: sqlite3.Connection, table: str, where_sql: str, params: tuple) -> int | None:
    row = conn.execute(f"SELECT id FROM {table} WHERE {where_sql} LIMIT 1", params).fetchone()
    return int(row[0]) if row else None

def insert_event_if_missing(conn: sqlite3.Connection, sample_id: int, *, event_type: str, to_status: str | None, message: str) -> bool:
    if not table_exists(conn, "sample_events"):
        return False
    cols = table_cols(conn, "sample_events")
    if "sample_id" not in cols:
        return False

    type_col = "event_type" if "event_type" in cols else ("type" if "type" in cols else None)
    msg_col = "message" if "message" in cols else ("note" if "note" in cols else ("details" if "details" in cols else None))

    # De-dupe if we can
    if type_col and msg_col:
        row = conn.execute(
            f"SELECT 1 FROM sample_events WHERE sample_id=? AND {type_col}=? AND {msg_col}=? LIMIT 1",
            (sample_id, event_type, message),
        ).fetchone()
        if row:
            return False

    ts = now_iso()
    payload = {"sample_id": sample_id}

    # event type
    if type_col:
        payload[type_col] = event_type

    # timestamps: set ALL that exist (covers schemas where multiple are NOT NULL)
    for k in ("occurred_at", "created_at", "timestamp", "ts"):
        if k in cols:
            payload[k] = ts

    # status delta (if schema supports)
    if "to_status" in cols and to_status is not None:
        payload["to_status"] = to_status
    if "from_status" in cols:
        payload["from_status"] = None

    # message
    if msg_col:
        payload[msg_col] = message

    keys = [k for k in payload.keys() if k in cols]
    if not keys:
        return False
    q = ",".join(["?"] * len(keys))
    sql = f"INSERT INTO sample_events ({', '.join(keys)}) VALUES ({q})"
    conn.execute(sql, [payload[k] for k in keys])
    return True


def _demo_container_is_exclusive(conn, container_id: int) -> bool:
    try:
        cols = table_cols(conn, "containers")
        if "exclusive" in cols:
            row = conn.execute("SELECT exclusive FROM containers WHERE id=? LIMIT 1", (container_id,)).fetchone()
            return bool(row and int(row[0]) == 1)
        # fallback: treat tube/vial as exclusive if explicit flag doesn't exist
        if "kind" in cols:
            row = conn.execute("SELECT kind FROM containers WHERE id=? LIMIT 1", (container_id,)).fetchone()
            k = (row[0] if row else "") or ""
            return str(k).strip().lower() in ("tube", "vial")
    except Exception:
        pass
    return False

def _demo_container_is_occupied(conn, container_id: int) -> bool:
    try:
        row = conn.execute("SELECT 1 FROM samples WHERE container_id=? LIMIT 1", (container_id,)).fetchone()
        return bool(row)
    except Exception:
        return False

def _demo_idx_from_external_id(external_id: str) -> int:
    # "S-001" -> 0, "S-012" -> 11; unknown -> 0
    m = re.search(r"(\\d+)", external_id or "")
    if not m:
        return 0
    try:
        return max(0, int(m.group(1)) - 1)
    except Exception:
        return 0

def _demo_choose_container(conn, external_id: str, exclusive_ids, fallback_id):
    idx = _demo_idx_from_external_id(external_id)
    # deterministic: first few samples try exclusive containers in order, rest go to fallback
    cid = None
    if exclusive_ids and idx < len(exclusive_ids):
        cid = exclusive_ids[idx]
        if cid and _demo_container_is_exclusive(conn, cid) and _demo_container_is_occupied(conn, cid):
            cid = None
    if cid is None:
        cid = fallback_id
    return cid

def main() -> int:
    ap = argparse.ArgumentParser(description="Seed deterministic demo data (idempotent).")
    ap.add_argument("--n", type=int, default=12, help="Number of samples to seed (default: 12)")
    args = ap.parse_args()

    db_path = os.environ.get("DB_PATH") or "data/lims.db"
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_db(conn)

        conn.execute("BEGIN")

        # Containers
        containers = [
            {"barcode": "TUBE-1", "kind": "tube",  "location": "bench-A"},
            {"barcode": "TUBE-2", "kind": "tube",  "location": "bench-A"},
            {"barcode": "VIAL-1", "kind": "vial",  "location": "bench-B"},
            {"barcode": "PLATE-1","kind": "plate", "location": "incubator-1"},
        ]
        for c in containers:
            payload = dict(c)
            ts = now_iso()
            for k in ("created_at", "occurred_at", "timestamp", "ts"):
                payload[k] = ts
            insert_or_ignore(conn, "containers", payload)

        tube1  = get_id(conn, "containers", "barcode = ?", ("TUBE-1",))
        tube2  = get_id(conn, "containers", "barcode = ?", ("TUBE-2",))
        vial1  = get_id(conn, "containers", "barcode = ?", ("VIAL-1",))
        plate1 = get_id(conn, "containers", "barcode = ?", ("PLATE-1",))

        # Demo rule: only 1 sample per exclusive container; remainder go to plate
        exclusive_ids = [cid for cid in (tube1, tube2, vial1) if cid]
        fallback_id = plate1

        exclusive_slots = [tube1, tube2, vial1]
        plate_slot = plate1

        # Samples
        for i in range(1, args.n + 1):
            ext = f"S-{i:03d}"
            st = STATUSES[(i - 1) % len(STATUSES)]
            cid = exclusive_slots[i - 1] if (i <= len(exclusive_slots) and exclusive_slots[i - 1] is not None) else plate_slot

            payload = {
                "external_id": ext,
                "status": st,
                "container_id": cid,
                "label": f"Demo Sample {ext}",
                "name": f"Demo Sample {ext}",
                "description": f"Seeded demo sample {ext}",
            }
            ts = now_iso()
            for k in ("created_at", "occurred_at", "timestamp", "ts"):
                payload[k] = ts

            # Choose a safe container (avoid exclusive-container constraint on reruns)

            ext = str(payload.get("external_id") or "").strip()

            if ext:

                try:

                    cid = _demo_choose_container(conn, ext, exclusive_ids, fallback_id)

                    if cid is not None:

                        payload["container_id"] = cid

                    else:

                        payload.pop("container_id", None)

                except Exception:

                    pass

            insert_or_ignore(conn, "samples", payload)

            sid = get_id(conn, "samples", "external_id = ?", (ext,))
            if sid is not None:
                insert_event_if_missing(conn, sid, event_type="seed", to_status=st, message=f"seeded {ext} ({st})")

        conn.commit()

        n_cont = conn.execute("SELECT COUNT(1) FROM containers").fetchone()[0]
        n_samp = conn.execute("SELECT COUNT(1) FROM samples").fetchone()[0]
        n_ev = conn.execute("SELECT COUNT(1) FROM sample_events").fetchone()[0] if table_exists(conn, "sample_events") else 0

        print(f"OK: seeded demo data into {db_path}")
        print(f"containers={n_cont} samples={n_samp} sample_events={n_ev} (events_table={'yes' if table_exists(conn,'sample_events') else 'no'})")
        return 0
    finally:
        conn.close()

if __name__ == "__main__":
    raise SystemExit(main())
