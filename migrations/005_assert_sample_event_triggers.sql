-- 005_assert_sample_event_triggers.sql: ensure sample event triggers exist (SQLite dev)
-- This is intentionally idempotent (IF NOT EXISTS) because 004 may have been partially pasted/corrupted.

CREATE TRIGGER IF NOT EXISTS trg_samples_ai_received
AFTER INSERT ON samples
BEGIN
  INSERT INTO sample_events (
    sample_id, event_type, from_container_id, to_container_id,
    old_status, new_status, note, occurred_at, created_at
  )
  VALUES (
    NEW.id, 'received', NULL, NEW.container_id,
    NULL, NEW.status, NEW.notes, NEW.received_at,
    strftime('%Y-%m-%dT%H:%M:%S+00:00','now')
  );
END;

CREATE TRIGGER IF NOT EXISTS trg_samples_ai_container_assigned
AFTER INSERT ON samples
WHEN NEW.container_id IS NOT NULL
BEGIN
  INSERT INTO sample_events (
    sample_id, event_type, from_container_id, to_container_id,
    old_status, new_status, note, occurred_at, created_at
  )
  VALUES (
    NEW.id, 'container_assigned', NULL, NEW.container_id,
    NULL, NEW.status, NEW.notes, NEW.received_at,
    strftime('%Y-%m-%dT%H:%M:%S+00:00','now')
  );
END;

CREATE TRIGGER IF NOT EXISTS trg_samples_au_container_assigned
AFTER UPDATE OF container_id ON samples
WHEN OLD.container_id IS NULL AND NEW.container_id IS NOT NULL
BEGIN
  INSERT INTO sample_events (
    sample_id, event_type, from_container_id, to_container_id,
    old_status, new_status, note, occurred_at, created_at
  )
  VALUES (
    NEW.id, 'container_assigned', NULL, NEW.container_id,
    NULL, NEW.status, NEW.notes,
    strftime('%Y-%m-%dT%H:%M:%S+00:00','now'),
    strftime('%Y-%m-%dT%H:%M:%S+00:00','now')
  );
END;

CREATE TRIGGER IF NOT EXISTS trg_samples_au_container_moved
AFTER UPDATE OF container_id ON samples
WHEN OLD.container_id IS NOT NULL AND NEW.container_id IS NOT NULL AND OLD.container_id != NEW.container_id
BEGIN
  INSERT INTO sample_events (
    sample_id, event_type, from_container_id, to_container_id,
    old_status, new_status, note, occurred_at, created_at
  )
  VALUES (
    NEW.id, 'container_moved', OLD.container_id, NEW.container_id,
    NULL, NEW.status, NULL,
    strftime('%Y-%m-%dT%H:%M:%S+00:00','now'),
    strftime('%Y-%m-%dT%H:%M:%S+00:00','now')
  );
END;

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
    OLD.status, NEW.status, NULL,
    strftime('%Y-%m-%dT%H:%M:%S+00:00','now'),
    strftime('%Y-%m-%dT%H:%M:%S+00:00','now')
  );
END;
