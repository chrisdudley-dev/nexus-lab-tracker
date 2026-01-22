-- 002_containers.sql: introduce containers + link samples -> containers

CREATE TABLE IF NOT EXISTS containers (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  barcode     TEXT UNIQUE NOT NULL,
  kind        TEXT NOT NULL,                -- e.g., tube, vial, plate
  location    TEXT,                         -- freeform for now
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

-- Add container_id to samples (SQLite allows ADD COLUMN; FK enforced via pragma + constraints on new table,
-- but for dev this is acceptable. We'll enforce FK at application-level for now, and improve later with a rebuild migration if needed.)
ALTER TABLE samples ADD COLUMN container_id INTEGER;

CREATE INDEX IF NOT EXISTS idx_containers_barcode ON containers(barcode);
CREATE INDEX IF NOT EXISTS idx_samples_container_id ON samples(container_id);
