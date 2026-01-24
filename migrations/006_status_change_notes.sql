-- 006_status_change_notes.sql: allow attaching a note to a status_changed event
--
-- SQLite triggers cannot see application parameters directly. For local/dev parity we
-- provide a small, transient context table that the CLI can populate within the same
-- transaction before updating samples.status.
--
-- Invariants:
-- - Rows are consumed and deleted by the trigger.
-- - If no row exists for a sample_id, note will be NULL.

CREATE TABLE IF NOT EXISTS sample_event_context (
  sample_id   INTEGER PRIMARY KEY,
  note        TEXT,
  created_at  TEXT NOT NULL
);

DROP TRIGGER IF EXISTS trg_samples_au_status_changed;

CREATE TRIGGER IF NOT EXISTS trg_samples_au_status_changed
AFTER UPDATE OF status ON samples
WHEN OLD.status != NEW.status
BEGIN
  INSERT INTO sample_events (
    sample_id, event_type, from_container_id, to_container_id,
    old_status, new_status, note, occurred_at, created_at
  )
  VALUES (
    NEW.id, 'status_changed', NULL, NEW.container_id,
    OLD.status, NEW.status,
    (SELECT c.note FROM sample_event_context c WHERE c.sample_id = NEW.id),
    strftime('%Y-%m-%dT%H:%M:%S+00:00','now'),
    strftime('%Y-%m-%dT%H:%M:%S+00:00','now')
  );

  DELETE FROM sample_event_context WHERE sample_id = NEW.id;
END;
