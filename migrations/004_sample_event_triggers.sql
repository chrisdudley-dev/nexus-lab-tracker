-- 004_sample_event_triggers.sql: automatic audit trail for samples (SQLite dev)

-- Backfill: ensure existing samples have baseline events
INSERT INTO sample_events (
  sample_id, event_type, from_container_id, to_container_id,
  old_status, new_status, note, occurred_at, created_at
)
SELECT
  s.id, 'received', NULL, s.container_id,
  NULL, s.status, s.notes, s.received_at,
  strftime('%Y-%m-%dT%H:%M:%S+00:00','now')
FROM samples s
WHERE NOT EXISTS (
  SELECT 1 FROM sample_events e
  WHERE e.sample_id = s.id AND e.event_type = 'received'
);

INSERT INTO sample_events (
  sample_id, event_type, from_container_id, to_container_id,
  old_status, new_status, note, occurred_at, created_at
)
SELECT
  s.id, 'container_assigned', NULL, s.container_id,
  NULL, s.status, s.notes, s.received_at,
  strftime('%Y-%m-%dT%H:%M:%S+00:00','now')
FROM samples s
WHERE s.container_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM sample_events e
    WHERE e.sample_id = s.id AND e.event_type = 'container_assigned'
  );

-- Trigger: always log sample received on insert
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

-- Trigger: log container assignment on insert if provided
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

-- Trigger: container assigned (NULL -> value)
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

-- Trigger: container moved (value -> different value)
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

-- Trigger: status changed
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
