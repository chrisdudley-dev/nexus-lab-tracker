-- 010_container_exclusive_flag.sql
-- Replace kind-hardcoded exclusivity with a container-level flag.

-- 1) Add flag (default non-exclusive)
ALTER TABLE containers ADD COLUMN is_exclusive INTEGER NOT NULL DEFAULT 0;

-- 2) Backfill: tube + vial are exclusive by default
UPDATE containers
SET is_exclusive = 1
WHERE lower(trim(kind)) IN ('tube','vial');

-- 3) Replace exclusivity triggers to consult containers.is_exclusive
DROP TRIGGER IF EXISTS trg_samples_bi_exclusive_container;
DROP TRIGGER IF EXISTS trg_samples_bu_exclusive_container;

CREATE TRIGGER trg_samples_bi_exclusive_container
BEFORE INSERT ON samples
WHEN NEW.container_id IS NOT NULL
  AND COALESCE((SELECT is_exclusive FROM containers WHERE id = NEW.container_id), 0) = 1
  AND EXISTS (SELECT 1 FROM samples s WHERE s.container_id = NEW.container_id)
BEGIN
  SELECT RAISE(ABORT, 'container is exclusive and already holds a sample');
END;

CREATE TRIGGER trg_samples_bu_exclusive_container
BEFORE UPDATE OF container_id ON samples
WHEN NEW.container_id IS NOT NULL
  AND NEW.container_id != OLD.container_id
  AND COALESCE((SELECT is_exclusive FROM containers WHERE id = NEW.container_id), 0) = 1
  AND EXISTS (SELECT 1 FROM samples s WHERE s.container_id = NEW.container_id)
BEGIN
  SELECT RAISE(ABORT, 'container is exclusive and already holds a sample');
END;
