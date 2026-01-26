-- 009_container_exclusivity.sql
-- Enforce exclusive occupancy for certain container kinds (tube, vial).
-- Rationale: prevents silent chain-of-custody errors (two samples "in" one tube).

DROP TRIGGER IF EXISTS trg_samples_bi_exclusive_container;
DROP TRIGGER IF EXISTS trg_samples_bu_exclusive_container;

CREATE TRIGGER trg_samples_bi_exclusive_container
BEFORE INSERT ON samples
WHEN NEW.container_id IS NOT NULL
  AND lower(trim((SELECT kind FROM containers WHERE id = NEW.container_id))) IN ('tube','vial')
  AND EXISTS (SELECT 1 FROM samples s WHERE s.container_id = NEW.container_id)
BEGIN
  SELECT RAISE(ABORT, 'container is exclusive and already holds a sample');
END;

CREATE TRIGGER trg_samples_bu_exclusive_container
BEFORE UPDATE OF container_id ON samples
WHEN NEW.container_id IS NOT NULL
  AND NEW.container_id != OLD.container_id
  AND lower(trim((SELECT kind FROM containers WHERE id = NEW.container_id))) IN ('tube','vial')
  AND EXISTS (SELECT 1 FROM samples s WHERE s.container_id = NEW.container_id)
BEGIN
  SELECT RAISE(ABORT, 'container is exclusive and already holds a sample');
END;
