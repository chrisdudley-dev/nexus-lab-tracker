-- 001_init.sql: initial LIMS schema (SQLite dev backend)
-- Note: schema_migrations table is managed by the migration runner.

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
