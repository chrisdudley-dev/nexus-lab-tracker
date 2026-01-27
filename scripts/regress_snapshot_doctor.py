#!/usr/bin/env python3
import json
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
    raise SystemExit(f"ERROR: rc={r.returncode} (expected {expect_rc}): {cmd}\n--- output ---\n{r.stdout}")
  return r.stdout

def parse_first_json_line(out: str):
  for line in out.splitlines():
    line = line.strip()
    if line.startswith("{") and line.endswith("}"):
      return json.loads(line)
  raise ValueError("no JSON line found")

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

  out = run(["./scripts/lims.sh", "snapshot", "doctor", str(tarball), "--json-only"], env, expect_rc=0)
  rep = parse_first_json_line(out)
  assert rep["ok"] is True
  assert rep["counts"]["samples"] == 1
  assert rep["counts"]["containers"] == 1
  assert rep["integrity_ok"] is True

  # Corrupt sqlite copy -> doctor should exit rc=2 (but still print JSON)
  snapdirs = sorted([p for p in exports.iterdir() if p.is_dir() and p.name.startswith("snapshot-")])
  src_db = snapdirs[0] / "lims.sqlite3"
  corrupt = td / "corrupt.sqlite3"
  corrupt.write_bytes(src_db.read_bytes())
  b = bytearray(corrupt.read_bytes())
  for i in range(min(64, len(b))):
    b[i] = 0
  corrupt.write_bytes(bytes(b))

  out2 = run(["./scripts/lims.sh", "snapshot", "doctor", str(corrupt), "--json-only"], env, expect_rc=2)
  rep2 = parse_first_json_line(out2)
  assert rep2["ok"] is False

print("OK: snapshot doctor regression passed (good snapshot OK; corrupt snapshot FAIL with JSON).")
