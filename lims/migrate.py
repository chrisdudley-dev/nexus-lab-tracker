from __future__ import annotations

import argparse
import json
from typing import List, Optional
from . import db


def cmd_status(_: argparse.Namespace) -> int:
  conn = db.connect()
  applied, pending = db.migration_status(conn)
  payload = {
    "db_path": str(db.db_path()),
    "applied": applied,
    "pending": pending,
  }
  print(json.dumps(payload, ensure_ascii=False, indent=2))
  return 0


def cmd_up(_: argparse.Namespace) -> int:
  conn = db.connect()
  applied_now = db.apply_migrations(conn)
  payload = {
    "db_path": str(db.db_path()),
    "applied_now": applied_now,
  }
  print(json.dumps(payload, ensure_ascii=False, indent=2))
  return 0


def build_parser() -> argparse.ArgumentParser:
  p = argparse.ArgumentParser(prog="lims-migrate", description="LIMS migration runner (SQLite dev backend)")
  sub = p.add_subparsers(dest="cmd", required=True)

  sp_status = sub.add_parser("status", help="Show applied/pending migrations")
  sp_status.set_defaults(fn=cmd_status)

  sp_up = sub.add_parser("up", help="Apply pending migrations")
  sp_up.set_defaults(fn=cmd_up)

  return p


def main(argv: Optional[List[str]] = None) -> int:
  parser = build_parser()
  args = parser.parse_args(argv)
  return int(args.fn(args))


if __name__ == "__main__":
  raise SystemExit(main())
