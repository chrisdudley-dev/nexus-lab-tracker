-- 012_guest_sessions.sql
-- Local-only guest sessions for the UI/API (no passwords; short-lived tokens).
-- Stored in SQLite for deterministic demos + audit correlation.

CREATE TABLE IF NOT EXISTS guest_sessions (
  id           TEXT PRIMARY KEY,
  display_name TEXT,
  created_at   TEXT NOT NULL,
  expires_at   TEXT NOT NULL,
  last_seen_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_guest_sessions_expires_at
  ON guest_sessions(expires_at);
