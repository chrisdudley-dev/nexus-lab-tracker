from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple, Union

from . import db


def utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_db(conn) -> None:
  # Be compatible with either style:
  # - migration-based: db.apply_migrations(conn)
  # - schema-based:    db.init_db(conn)
  if hasattr(db, "apply_migrations"):
    db.apply_migrations(conn)  # type: ignore[attr-defined]
  elif hasattr(db, "init_db"):
    db.init_db(conn)  # type: ignore[attr-defined]
  else:
    raise RuntimeError("db module missing apply_migrations/init_db")


def print_rows(rows) -> None:
  rows = list(rows)
  if not rows:
    print("(no results)")
    return
  cols = rows[0].keys()
  for r in rows:
    obj = {k: r[k] for k in cols}
    print(json.dumps(obj, ensure_ascii=False))


def parse_identifier(s: str) -> Tuple[str, Union[int, str]]:
  if re.fullmatch(r"\d+", s):
    return ("id", int(s))
  return ("external_id", s)



def resolve_sample_id(conn, identifier: str) -> Optional[int]:
  key, value = parse_identifier(identifier)
  row = conn.execute(f"SELECT id FROM samples WHERE {key} = ?", (value,)).fetchone()
  if not row:
    return None
  return int(row["id"])

def log_sample_event(
  conn,
  sample_id: int,
  event_type: str,
  *,
  from_container_id: Optional[int] = None,
  to_container_id: Optional[int] = None,
  old_status: Optional[str] = None,
  new_status: Optional[str] = None,
  note: Optional[str] = None,
  occurred_at: Optional[str] = None,
) -> None:
  now = utc_now_iso()
  when = occurred_at or now
  conn.execute(
    """
    INSERT INTO sample_events
      (sample_id, event_type, from_container_id, to_container_id, old_status, new_status, note, occurred_at, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (sample_id, event_type, from_container_id, to_container_id, old_status, new_status, note, when, now),
  )

def parse_container_identifier(s: str) -> Tuple[str, Union[int, str]]:
  if re.fullmatch(r"\d+", s):
    return ("id", int(s))
  return ("barcode", s)


def generate_external_id(prefix: str = "DEV") -> str:
  # Deterministic-ish, human friendly
  ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
  return f"{prefix}-{ts}"


def resolve_container_id(conn, identifier: str) -> Optional[int]:
  key, value = parse_container_identifier(identifier)
  row = conn.execute(f"SELECT id FROM containers WHERE {key} = ?", (value,)).fetchone()
  if not row:
    return None
  return int(row["id"])


def cmd_init(_: argparse.Namespace) -> int:
  conn = db.connect()
  ensure_db(conn)
  print(f"OK: initialized LIMS DB at {db.db_path()}")
  return 0


# -----------------
# Container commands
# -----------------
def cmd_container_add(args: argparse.Namespace) -> int:
  conn = db.connect()
  ensure_db(conn)
  now = utc_now_iso()
  cur = conn.cursor()
  cur.execute(
    """
    INSERT INTO containers (barcode, kind, location, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?)
    """,
    (args.barcode, args.kind, args.location, now, now),
  )
  conn.commit()
  cid = cur.lastrowid
  row = conn.execute("SELECT * FROM containers WHERE id = ?", (cid,)).fetchone()
  print("OK: container created")
  print_rows([row])
  return 0


def cmd_container_list(args: argparse.Namespace) -> int:
  conn = db.connect()
  ensure_db(conn)
  sql = "SELECT * FROM containers ORDER BY created_at DESC"
  params: List[Any] = []
  if args.limit:
    sql += " LIMIT ?"
    params.append(args.limit)
  rows = conn.execute(sql, params).fetchall()
  print_rows(rows)
  return 0


def cmd_container_get(args: argparse.Namespace) -> int:
  conn = db.connect()
  ensure_db(conn)
  key, value = parse_container_identifier(args.identifier)
  row = conn.execute(f"SELECT * FROM containers WHERE {key} = ?", (value,)).fetchone()
  if not row:
    print("NOT FOUND")
    return 2
  print_rows([row])
  return 0


# --------------
# Sample commands
# --------------
def cmd_sample_add(args: argparse.Namespace) -> int:
  conn = db.connect()
  ensure_db(conn)

  now = utc_now_iso()
  received_at = args.received_at or now
  external_id = args.external_id or generate_external_id("DEV")

  container_id: Optional[int] = None
  if args.container:
    container_id = resolve_container_id(conn, args.container)
    if container_id is None:
      print(f"NOT FOUND: container '{args.container}'")
      return 2

  cur = conn.cursor()
  cur.execute(
    """
    INSERT INTO samples (external_id, specimen_type, status, notes, received_at, created_at, updated_at, container_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (external_id, args.specimen_type, args.status, args.notes, received_at, now, now, container_id),
  )
  conn.commit()
  sample_id = cur.lastrowid
  row = conn.execute("SELECT * FROM samples WHERE id = ?", (sample_id,)).fetchone()
  print("OK: sample created")
  print_rows([row])
  return 0


def cmd_sample_list(args: argparse.Namespace) -> int:
  conn = db.connect()
  ensure_db(conn)

  where = []
  params: List[Any] = []
  if args.status:
    where.append("status = ?")
    params.append(args.status)
  if args.container:
    cid = resolve_container_id(conn, args.container)
    if cid is None:
      print(f"NOT FOUND: container '{args.container}'")
      return 2
    where.append("container_id = ?")
    params.append(cid)

  sql = "SELECT * FROM samples"
  if where:
    sql += " WHERE " + " AND ".join(where)
  sql += " ORDER BY received_at DESC"
  if args.limit:
    sql += " LIMIT ?"
    params.append(args.limit)

  rows = conn.execute(sql, params).fetchall()
  print_rows(rows)
  return 0


def cmd_sample_get(args: argparse.Namespace) -> int:
  conn = db.connect()
  ensure_db(conn)
  key, value = parse_identifier(args.identifier)
  row = conn.execute(f"SELECT * FROM samples WHERE {key} = ?", (value,)).fetchone()
  if not row:
    print("NOT FOUND")
    return 2
  print_rows([row])
  return 0



def cmd_sample_events(args: argparse.Namespace) -> int:
  conn = db.connect()
  ensure_db(conn)
  sid = resolve_sample_id(conn, args.identifier)
  if sid is None:
    print("NOT FOUND")
    return 2
  rows = conn.execute(
    """
    SELECT *
    FROM sample_events
    WHERE sample_id = ?
    ORDER BY occurred_at DESC, id DESC
    LIMIT ?
    """,
    (sid, args.limit),
  ).fetchall()
  print_rows(rows)
  return 0

def cmd_sample_move(args: argparse.Namespace) -> int:
  conn = db.connect()
  ensure_db(conn)

  # Resolve sample
  key, value = parse_identifier(args.sample)
  sample = conn.execute(f"SELECT * FROM samples WHERE {key} = ?", (value,)).fetchone()
  if not sample:
    print("NOT FOUND: sample")
    return 2

  # Resolve container
  cid = resolve_container_id(conn, args.to)
  if cid is None:
    print(f"NOT FOUND: container '{args.to}'")
    return 2

  now = utc_now_iso()
  conn.execute(
    "UPDATE samples SET container_id = ?, updated_at = ? WHERE id = ?",
    (cid, now, int(sample["id"])),
  )
  conn.commit()

  row = conn.execute("SELECT * FROM samples WHERE id = ?", (int(sample["id"]),)).fetchone()
  print("OK: sample moved")
  print_rows([row])
  return 0


def cmd_sample_status(args: argparse.Namespace) -> int:
  conn = db.connect()
  ensure_db(conn)

  sid = resolve_sample_id(conn, args.identifier)
  if sid is None:
    print("NOT FOUND")
    return 2

  sample = conn.execute("SELECT * FROM samples WHERE id = ?", (sid,)).fetchone()
  if not sample:
    print("NOT FOUND")
    return 2

  old = str(sample["status"])
  new = str(args.to)

  if old == new:
    print(f"OK: sample already in status '{new}'")
    print_rows([sample])
    return 0

  now = utc_now_iso()

  # If a note is provided, stash it in a transient context table so the
  # status_changed trigger can attach it to the generated audit event.
  if args.note:
    conn.execute(
      "INSERT OR REPLACE INTO sample_event_context (sample_id, note, created_at) VALUES (?, ?, ?)",
      (sid, args.note, now),
    )

  conn.execute(
    "UPDATE samples SET status = ?, updated_at = ? WHERE id = ?",
    (new, now, sid),
  )
  conn.commit()

  row = conn.execute("SELECT * FROM samples WHERE id = ?", (sid,)).fetchone()
  print("OK: sample status updated")
  print_rows([row])
  return 0


def build_parser() -> argparse.ArgumentParser:
  p = argparse.ArgumentParser(prog="lims", description="Minimal LIMS CLI (SQLite dev backend)")
  sub = p.add_subparsers(dest="cmd", required=True)

  sp_init = sub.add_parser("init", help="Initialize local LIMS database")
  sp_init.set_defaults(fn=cmd_init)

  sp_container = sub.add_parser("container", help="Container operations")
  csub = sp_container.add_subparsers(dest="container_cmd", required=True)

  sp_cadd = csub.add_parser("add", help="Add a container")
  sp_cadd.add_argument("--barcode", required=True, help="Container barcode (unique)")
  sp_cadd.add_argument("--kind", required=True, help="Kind (tube/vial/plate/etc)")
  sp_cadd.add_argument("--location", default=None, help="Optional location string")
  sp_cadd.set_defaults(fn=cmd_container_add)

  sp_clist = csub.add_parser("list", help="List containers")
  sp_clist.add_argument("--limit", type=int, default=25, help="Max rows (default: 25)")
  sp_clist.set_defaults(fn=cmd_container_list)

  sp_cget = csub.add_parser("get", help="Get a container by ID or barcode")
  sp_cget.add_argument("identifier", help="Numeric id or barcode")
  sp_cget.set_defaults(fn=cmd_container_get)

  sp_sample = sub.add_parser("sample", help="Sample intake operations")
  sample_sub = sp_sample.add_subparsers(dest="sample_cmd", required=True)

  sp_add = sample_sub.add_parser("add", help="Add a sample")
  sp_add.add_argument("--external-id", default=None, help="Optional external/sample accession ID")
  sp_add.add_argument("--specimen-type", required=True, help="Specimen type (e.g., blood, saliva, tissue)")
  sp_add.add_argument("--status", default="received", help="Status (default: received)")
  sp_add.add_argument("--notes", default=None, help="Freeform notes")
  sp_add.add_argument("--received-at", default=None, help="ISO8601 UTC timestamp (default: now)")
  sp_add.add_argument("--container", default=None, help="Assign to container (id or barcode)")
  sp_add.set_defaults(fn=cmd_sample_add)

  sp_list = sample_sub.add_parser("list", help="List samples")
  sp_list.add_argument("--status", default=None, help="Filter by status")
  sp_list.add_argument("--container", default=None, help="Filter by container (id or barcode)")
  sp_list.add_argument("--limit", type=int, default=25, help="Max rows (default: 25)")
  sp_list.set_defaults(fn=cmd_sample_list)

  sp_get = sample_sub.add_parser("get", help="Get a sample by ID or external_id")
  sp_get.add_argument("identifier", help="Numeric id or external_id")
  sp_get.set_defaults(fn=cmd_sample_get)

  sp_events = sample_sub.add_parser("events", help="List audit events for a sample")
  sp_events.add_argument("identifier", help="Numeric id or external_id")
  sp_events.add_argument("--limit", type=int, default=50, help="Max rows (default: 50)")
  sp_events.set_defaults(fn=cmd_sample_events)


  sp_move = sample_sub.add_parser("move", help="Move a sample to a container")
  sp_move.add_argument("sample", help="Sample id or external_id")
  sp_move.add_argument("--to", required=True, help="Target container id or barcode")
  sp_move.set_defaults(fn=cmd_sample_move)

  sp_status = sample_sub.add_parser("status", help="Change a sample's status")
  sp_status.add_argument("identifier", help="Numeric id or external_id")
  sp_status.add_argument("--to", required=True, help="New status value")
  sp_status.add_argument("--note", default=None, help="Optional note to attach to the status change event")
  sp_status.set_defaults(fn=cmd_sample_status)

  return p


def main(argv: Optional[List[str]] = None) -> int:
  parser = build_parser()
  args = parser.parse_args(argv)
  return int(args.fn(args))


if __name__ == "__main__":
  raise SystemExit(main())
