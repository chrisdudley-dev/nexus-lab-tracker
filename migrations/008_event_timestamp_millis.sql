-- 008_event_timestamp_millis.sql: recreate sample event triggers with millisecond timestamps
-- Optional: improves timestamp-only ordering under high event throughput.

DROP TRIGGER IF EXISTS trg_samples_ai_received;
CREATE TRIGGER trg_samples_ai_received
AFTER INSERT ON samples
BEGIN
  INSERT INTO sample_events (
    sample_id, event_type, from_container_id, to_container_id,
    old_status, new_status, note, occurred_at, created_at
  )
  VALUES (
    NEW.id, 'received', NULL, NEW.container_id,
    NULL, NEW.status, NEW.notes, NEW.received_at,
    strftime('%Y-%m-%dT%H:%M:%f+00:00','now')
  );
END;

DROP TRIGGER IF EXISTS trg_samples_ai_container_assigned;
CREATE TRIGGER trg_samples_ai_container_assigned
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
    strftime('%Y-%m-%dT%H:%M:%f+00:00','now')
  );
END;

DROP TRIGGER IF EXISTS trg_samples_au_container_assigned;
CREATE TRIGGER trg_samples_au_container_assigned
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
    strftime('%Y-%m-%dT%H:%M:%f+00:00','now'),
    strftime('%Y-%m-%dT%H:%M:%f+00:00','now')
  );
END;

DROP TRIGGER IF EXISTS trg_samples_au_status_changed;
CREATE TRIGGER trg_samples_au_status_changed
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
    strftime('%Y-%m-%dT%H:%M:%f+00:00','now'),
    strftime('%Y-%m-%dT%H:%M:%f+00:00','now')
  );

  DELETE FROM sample_event_context WHERE sample_id = NEW.id;
END;

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
    strftime('%Y-%m-%dT%H:%M:%f+00:00','now'),
    strftime('%Y-%m-%dT%H:%M:%f+00:00','now')
  );

  DELETE FROM sample_event_context WHERE sample_id = NEW.id;
END;
