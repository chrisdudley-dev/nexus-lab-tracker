from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS samples (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  external_id   TEXT UNIQUE,
  specimen_type TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'received',
  notes         TEXT,
  received_at   TEXT NOT NULL,          -- ISO8601 UTC string
  created_at    TEXT NOT NULL,          -- ISO8601 UTC string
  updated_at    TEXT NOT NULL           -- ISO8601 UTC string
);

CREATE INDEX IF NOT EXISTS idx_samples_status ON samples(status);
CREATE INDEX IF NOT EXISTS idx_samples_received_at ON samples(received_at);
"""

def db_path() -> Path:
  # Prefer explicit env override; otherwise default to ./data/lims.sqlite3
  p = os.environ.get("DB_PATH")
  if p:
    return Path(p).expanduser()
  return Path("data") / "lims.sqlite3"

def connect() -> sqlite3.Connection:
  path = db_path()
  path.parent.mkdir(parents=True, exist_ok=True)
  conn = sqlite3.connect(str(path))
  conn.row_factory = sqlite3.Row
  conn.execute("PRAGMA foreign_keys = ON;")
  return conn

def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
  close_after = False
  if conn is None:
    conn = connect()
    close_after = True
  try:
    conn.executescript(SCHEMA_SQL)
    conn.commit()
  finally:
    if close_after:
      conn.close()
