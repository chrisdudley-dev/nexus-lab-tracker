from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set, Tuple


def utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_root() -> Optional[Path]:
  rr = os.environ.get("REPO_ROOT")
  if not rr:
    return None
  return Path(rr).expanduser()


def db_path() -> Path:
  # Prefer explicit env override; otherwise default to ./data/lims.sqlite3
  p = os.environ.get("DB_PATH")
  if p:
    path = Path(p).expanduser()
    # If relative, anchor to REPO_ROOT when available (more deterministic across shells).
    if not path.is_absolute():
      rr = repo_root()
      if rr:
        return rr / path
    return path

  rr = repo_root()
  if rr:
    return rr / "data" / "lims.sqlite3"
  return Path("data") / "lims.sqlite3"


def connect() -> sqlite3.Connection:
  path = db_path()
  path.parent.mkdir(parents=True, exist_ok=True)
  conn = sqlite3.connect(str(path))
  conn.row_factory = sqlite3.Row
  conn.execute("PRAGMA foreign_keys = ON;")
  return conn


def migrations_dir() -> Path:
  # repo_root/lims/db.py -> repo_root
  rr = Path(__file__).resolve().parent.parent
  return rr / "migrations"


def ensure_schema_migrations(conn: sqlite3.Connection) -> None:
  conn.execute(
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
      id         TEXT PRIMARY KEY,
      applied_at TEXT NOT NULL
    );
    """
  )
  conn.commit()


def applied_migrations(conn: sqlite3.Connection) -> Set[str]:
  ensure_schema_migrations(conn)
  rows = conn.execute("SELECT id FROM schema_migrations ORDER BY id").fetchall()
  return {r["id"] for r in rows}


def available_migrations() -> List[Tuple[str, Path]]:
  mdir = migrations_dir()
  if not mdir.exists():
    return []
  paths = sorted(mdir.glob("*.sql"))
  out: List[Tuple[str, Path]] = []
  for p in paths:
    mid = p.stem  # e.g. "001_init"
    out.append((mid, p))
  return out


def apply_migrations(conn: sqlite3.Connection) -> List[str]:
  ensure_schema_migrations(conn)
  already = applied_migrations(conn)
  applied_now: List[str] = []

  for mid, path in available_migrations():
    if mid in already:
      continue
    sql = path.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.execute(
      "INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)",
      (mid, utc_now_iso()),
    )
    conn.commit()
    applied_now.append(mid)

  return applied_now


def migration_status(conn: sqlite3.Connection) -> Tuple[List[str], List[str]]:
  already = sorted(applied_migrations(conn))
  available = [mid for mid, _ in available_migrations()]
  pending = [m for m in available if m not in set(already)]
  return already, pending


def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
  close_after = False
  if conn is None:
    conn = connect()
    close_after = True
  try:
    apply_migrations(conn)
  finally:
    if close_after:
      conn.close()
