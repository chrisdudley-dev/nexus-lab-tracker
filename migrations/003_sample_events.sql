-- 003_sample_events.sql: chain of custody / audit trail for samples

CREATE TABLE IF NOT EXISTS sample_events (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  sample_id          INTEGER NOT NULL,
  event_type         TEXT NOT NULL,          -- e.g., received, container_assigned, container_moved, status_changed, note
  from_container_id  INTEGER,                -- optional
  to_container_id    INTEGER,                -- optional
  old_status         TEXT,                   -- optional
  new_status         TEXT,                   -- optional
  note               TEXT,                   -- optional freeform
  occurred_at        TEXT NOT NULL,          -- ISO8601 UTC string
  created_at         TEXT NOT NULL,          -- ISO8601 UTC string

  -- For SQLite dev: FK enforcement depends on PRAGMA foreign_keys=ON (we already do this in connect()).
  FOREIGN KEY(sample_id) REFERENCES samples(id)
);

CREATE INDEX IF NOT EXISTS idx_sample_events_sample_id ON sample_events(sample_id);
CREATE INDEX IF NOT EXISTS idx_sample_events_occurred_at ON sample_events(occurred_at);
