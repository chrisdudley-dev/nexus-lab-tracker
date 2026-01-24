-- 007_container_move_notes.sql: allow attaching a note to a container_moved event

-- Ensure the context table exists (introduced in 006, but keep robust for fresh DBs).
CREATE TABLE IF NOT EXISTS sample_event_context (
  sample_id   INTEGER PRIMARY KEY,
  note        TEXT,
  created_at  TEXT NOT NULL
);

DROP TRIGGER IF EXISTS trg_samples_au_container_moved;

CREATE TRIGGER trg_samples_au_container_moved
AFTER UPDATE OF container_id ON samples
WHEN OLD.container_id IS NOT NEW.container_id
BEGIN
  INSERT INTO sample_events (
    sample_id, event_type, from_container_id, to_container_id,
    old_status, new_status, note, occurred_at, created_at
  )
  VALUES (
    NEW.id, 'container_moved', OLD.container_id, NEW.container_id,
    OLD.status, NEW.status,
    (SELECT c.note FROM sample_event_context c WHERE c.sample_id = NEW.id),
    strftime('%Y-%m-%dT%H:%M:%S+00:00','now'),
    strftime('%Y-%m-%dT%H:%M:%S+00:00','now')
  );

  DELETE FROM sample_event_context WHERE sample_id = NEW.id;
END;
