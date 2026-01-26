-- 011_container_kind_defaults.sql
-- Centralize container-kind defaults (e.g., exclusive occupancy) and apply them automatically.

-- 1) Defaults table (extend over time)
CREATE TABLE IF NOT EXISTS container_kind_defaults (
  kind TEXT PRIMARY KEY,
  is_exclusive INTEGER NOT NULL CHECK (is_exclusive IN (0,1))
);

-- 2) Seed defaults: tube/vial are exclusive by default
INSERT OR REPLACE INTO container_kind_defaults(kind, is_exclusive) VALUES
  ('tube', 1),
  ('vial', 1);

-- 3) Backfill existing containers to match defaults (covers any created after 010)
UPDATE containers
SET is_exclusive = (
  SELECT d.is_exclusive
  FROM container_kind_defaults d
  WHERE d.kind = lower(trim(containers.kind))
)
WHERE EXISTS (
  SELECT 1 FROM container_kind_defaults d
  WHERE d.kind = lower(trim(containers.kind))
);

-- 4) Apply defaults automatically to newly created containers
DROP TRIGGER IF EXISTS trg_containers_ai_apply_kind_defaults;

CREATE TRIGGER trg_containers_ai_apply_kind_defaults
AFTER INSERT ON containers
WHEN EXISTS (
  SELECT 1 FROM container_kind_defaults d
  WHERE d.kind = lower(trim(NEW.kind))
)
BEGIN
  UPDATE containers
  SET is_exclusive = (
    SELECT d.is_exclusive
    FROM container_kind_defaults d
    WHERE d.kind = lower(trim(NEW.kind))
  )
  WHERE id = NEW.id;
END;
