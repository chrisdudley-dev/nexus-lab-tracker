#!/usr/bin/env python3
import os
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

def run(cmd, env, expect_rc=0):
  r = subprocess.run(
    cmd, cwd=REPO, env=env, text=True,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT
  )
  if r.returncode != expect_rc:
    raise SystemExit(
      f"ERROR: rc={r.returncode} (expected {expect_rc}): {cmd}\n--- output ---\n{r.stdout}"
    )
  return r.stdout

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
  run(["./scripts/lims.sh", "container", "add", "--barcode", "TUBE-A", "--kind", "tube"], env)
  run(["./scripts/lims.sh", "sample", "add", "--external-id", "S-001", "--specimen-type", "blood", "--container", "TUBE-A"], env)
  run(["./scripts/lims.sh", "snapshot", "export"], env)

  tars = list(exports.glob("snapshot-*.tar.gz"))
  if len(tars) != 1:
    raise SystemExit(f"ERROR: expected 1 snapshot tarball, found {len(tars)}")
  tarball = tars[0]

  out = run(["./scripts/lims.sh", "snapshot", "verify", str(tarball)], env)
  if "OK: snapshot verify complete." not in out:
    raise SystemExit(f"ERROR: verify did not complete successfully:\n{out}")

  snapdirs = sorted([p for p in exports.iterdir() if p.is_dir() and p.name.startswith("snapshot-")])
  src_db = snapdirs[0] / "lims.sqlite3"
  corrupt = td / "corrupt.sqlite3"
  corrupt.write_bytes(src_db.read_bytes())

  b = bytearray(corrupt.read_bytes())
  for i in range(min(64, len(b))):
    b[i] = 0
  corrupt.write_bytes(bytes(b))

  out2 = run(["./scripts/lims.sh", "snapshot", "verify", str(corrupt)], env, expect_rc=2)
  if "integrity_check" not in out2 and "ERROR:" not in out2:
    raise SystemExit(f"ERROR: expected integrity failure output, got:\n{out2}")

print("OK: snapshot verify regression passed (good tarball ok, corrupt sqlite rejected).")
