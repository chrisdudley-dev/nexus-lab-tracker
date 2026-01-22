from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from . import db

def utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def print_rows(rows) -> None:
  # Compact, readable output without external dependencies.
  rows = list(rows)
  if not rows:
    print("(no results)")
    return
  # Column order preference:
  cols = rows[0].keys()
  for r in rows:
    obj = {k: r[k] for k in cols}
    print(json.dumps(obj, ensure_ascii=False))

def parse_identifier(s: str) -> Tuple[str, Union[int, str]]:
  # If purely numeric -> treat as internal id; else external_id
  if re.fullmatch(r"\d+", s):
    return ("id", int(s))
  return ("external_id", s)

def cmd_init(_: argparse.Namespace) -> int:
  conn = db.connect()
  db.init_db(conn)
  print(f"OK: initialized LIMS DB at {db.db_path()}")
  return 0

def cmd_sample_add(args: argparse.Namespace) -> int:
  conn = db.connect()
  db.init_db(conn)

  now = utc_now_iso()
  received_at = args.received_at or now

  cur = conn.cursor()
  try:
    cur.execute(
      """
      INSERT INTO samples (external_id, specimen_type, status, notes, received_at, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?)
      """,
      (args.external_id, args.specimen_type, args.status, args.notes, received_at, now, now),
    )
    conn.commit()
  except Exception as e:
    conn.rollback()
    raise

  sample_id = cur.lastrowid
  row = conn.execute("SELECT * FROM samples WHERE id = ?", (sample_id,)).fetchone()
  print("OK: sample created")
  print_rows([row])
  return 0

def cmd_sample_list(args: argparse.Namespace) -> int:
  conn = db.connect()
  db.init_db(conn)

  where = []
  params: List[Any] = []

  if args.status:
    where.append("status = ?")
    params.append(args.status)

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
  db.init_db(conn)

  key, value = parse_identifier(args.identifier)
  row = conn.execute(f"SELECT * FROM samples WHERE {key} = ?", (value,)).fetchone()
  if not row:
    print("NOT FOUND")
    return 2
  print_rows([row])
  return 0

def build_parser() -> argparse.ArgumentParser:
  p = argparse.ArgumentParser(prog="lims", description="Minimal LIMS CLI (SQLite dev backend)")
  sub = p.add_subparsers(dest="cmd", required=True)

  sp_init = sub.add_parser("init", help="Initialize local LIMS database")
  sp_init.set_defaults(fn=cmd_init)

  sp_sample = sub.add_parser("sample", help="Sample intake operations")
  sample_sub = sp_sample.add_subparsers(dest="sample_cmd", required=True)

  sp_add = sample_sub.add_parser("add", help="Add a sample")
  sp_add.add_argument("--external-id", help="Optional external/sample accession ID", default=None)
  sp_add.add_argument("--specimen-type", required=True, help="Specimen type (e.g., blood, saliva, tissue)")
  sp_add.add_argument("--status", default="received", help="Status (default: received)")
  sp_add.add_argument("--notes", default=None, help="Freeform notes")
  sp_add.add_argument("--received-at", default=None, help="ISO8601 UTC timestamp (default: now)")
  sp_add.set_defaults(fn=cmd_sample_add)

  sp_list = sample_sub.add_parser("list", help="List samples")
  sp_list.add_argument("--status", default=None, help="Filter by status")
  sp_list.add_argument("--limit", type=int, default=25, help="Max rows (default: 25)")
  sp_list.set_defaults(fn=cmd_sample_list)

  sp_get = sample_sub.add_parser("get", help="Get a sample by ID or external_id")
  sp_get.add_argument("identifier", help="Numeric id or external_id")
  sp_get.set_defaults(fn=cmd_sample_get)

  return p

def main(argv: Optional[List[str]] = None) -> int:
  parser = build_parser()
  args = parser.parse_args(argv)
  return int(args.fn(args))

if __name__ == "__main__":
  raise SystemExit(main())
