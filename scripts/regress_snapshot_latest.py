#!/usr/bin/env python3
import os
import subprocess
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

def run(cmd, env, expect_rc=0):
  r = subprocess.run(
    cmd, cwd=REPO, env=env, text=True,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT
  )
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

  # Snapshot 1
  run(["./scripts/lims.sh", "init"], env)
  run(["./scripts/migrate.sh", "up"], env)
  run(["./scripts/lims.sh", "container", "add", "--barcode", "TUBE-A", "--kind", "tube"], env)
  run(["./scripts/lims.sh", "sample", "add", "--external-id", "S-001", "--specimen-type", "blood", "--container", "TUBE-A"], env)
  run(["./scripts/lims.sh", "snapshot", "export"], env)

  # Ensure second export won’t overwrite same-second filename
  time.sleep(1.2)

  # Snapshot 2
  run(["./scripts/lims.sh", "container", "add", "--barcode", "TUBE-B", "--kind", "tube"], env)
  run(["./scripts/lims.sh", "sample", "add", "--external-id", "S-002", "--specimen-type", "blood", "--container", "TUBE-B"], env)
  run(["./scripts/lims.sh", "snapshot", "export"], env)

  tars = sorted(exports.glob("snapshot-*.tar.gz"))
  if len(tars) != 2:
    raise SystemExit(f"ERROR: expected 2 tarballs, found {len(tars)}: {[p.name for p in tars]}")

  expected_latest = str(tars[1].resolve())
  expected_prev = str(tars[0].resolve())

  got_latest = run(["./scripts/lims.sh", "snapshot", "latest"], env)
  got_prev = run(["./scripts/lims.sh", "snapshot", "latest", "--n", "2"], env)

  if str(Path(got_latest).resolve()) != expected_latest:
    raise SystemExit(f"ERROR: latest mismatch\nexpected: {expected_latest}\ngot:      {got_latest}")

  if str(Path(got_prev).resolve()) != expected_prev:
    raise SystemExit(f"ERROR: latest --n 2 mismatch\nexpected: {expected_prev}\ngot:      {got_prev}")

print("OK: snapshot latest regression passed (N=1 newest, N=2 previous).")
