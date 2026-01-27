#!/usr/bin/env python3
import os, subprocess, tempfile, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

def run(cmd, env, expect_rc=0):
  r = subprocess.run(cmd, cwd=REPO, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
  if r.returncode != expect_rc:
    raise SystemExit(f"ERROR: rc={r.returncode} (expected {expect_rc}): {cmd}\n--- output ---\n{r.stdout}")
  return r.stdout.strip()

with tempfile.TemporaryDirectory() as td:
  td = Path(td)
  exports = td / "exports"
  exports.mkdir(parents=True, exist_ok=True)
  db = td / "db.sqlite3"

  env = os.environ.copy()
  env["DB_PATH"] = str(db)
  env["EXPORTS_DIR"] = str(exports)

  run(["./scripts/lims.sh", "init"], env)
  run(["./scripts/migrate.sh", "up"], env)

  # Make 3 snapshots (ensure unique filenames)
  run(["./scripts/lims.sh", "container", "add", "--barcode", "T1", "--kind", "tube"], env)
  run(["./scripts/lims.sh", "sample", "add", "--external-id", "S1", "--specimen-type", "blood", "--container", "T1"], env)
  run(["./scripts/lims.sh", "snapshot", "export"], env)
  time.sleep(1.2)

  run(["./scripts/lims.sh", "container", "add", "--barcode", "T2", "--kind", "tube"], env)
  run(["./scripts/lims.sh", "sample", "add", "--external-id", "S2", "--specimen-type", "blood", "--container", "T2"], env)
  run(["./scripts/lims.sh", "snapshot", "export"], env)
  time.sleep(1.2)

  run(["./scripts/lims.sh", "container", "add", "--barcode", "T3", "--kind", "tube"], env)
  run(["./scripts/lims.sh", "sample", "add", "--external-id", "S3", "--specimen-type", "blood", "--container", "T3"], env)
  run(["./scripts/lims.sh", "snapshot", "export"], env)

  tars = sorted(exports.glob("snapshot-*.tar.gz"))
  if len(tars) != 3:
    raise SystemExit(f"ERROR: expected 3 tarballs, found {len(tars)}: {[p.name for p in tars]}")

  oldest = tars[0].name
  newest = tars[2].name

  # Pin the oldest
  run(["./scripts/lims.sh", "snapshot", "pin", oldest], env)

  # Dry-run prune keep=1 should delete only the middle, but not actually delete
  run(["./scripts/lims.sh", "snapshot", "prune", "--keep", "1", "--dry-run"], env)
  tars_after = sorted(exports.glob("snapshot-*.tar.gz"))
  if len(tars_after) != 3:
    raise SystemExit("ERROR: dry-run prune should not delete files")

  # Apply prune keep=1 should keep newest + pinned oldest => 2 remain
  run(["./scripts/lims.sh", "snapshot", "prune", "--keep", "1", "--apply"], env)
  remain = sorted([p.name for p in exports.glob("snapshot-*.tar.gz")])
  if sorted(remain) != sorted([oldest, newest]):
    raise SystemExit(f"ERROR: expected only oldest+pinned and newest remain; got: {remain}")

  # Unpin oldest and prune again -> only newest should remain
  run(["./scripts/lims.sh", "snapshot", "unpin", oldest], env)
  run(["./scripts/lims.sh", "snapshot", "prune", "--keep", "1", "--apply"], env)
  remain2 = sorted([p.name for p in exports.glob("snapshot-*.tar.gz")])
  if remain2 != [newest]:
    raise SystemExit(f"ERROR: expected only newest remain after unpin+prune; got: {remain2}")

print("OK: snapshot prune regression passed (dry-run safe; apply prunes; pins preserved).")
