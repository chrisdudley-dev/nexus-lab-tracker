#!/usr/bin/env python3
import json
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

def parse_first_json_line(out: str):
  for line in out.splitlines():
    line = line.strip()
    if line.startswith("{") and line.endswith("}"):
      return json.loads(line)
  raise SystemExit("ERROR: no JSON object line found in output")

with tempfile.TemporaryDirectory() as td:
  td = Path(td)
  exports = td / "exports"
  exports.mkdir(parents=True, exist_ok=True)

  db = td / "db.sqlite3"
  env = os.environ.copy()
  env["DB_PATH"] = str(db)
  env["EXPORTS_DIR"] = str(exports)

  # Create snapshot #1
  run(["./scripts/lims.sh", "init"], env)
  run(["./scripts/migrate.sh", "up"], env)

  run(["./scripts/lims.sh", "container", "add", "--barcode", "TUBE-A", "--kind", "tube"], env)
  run(["./scripts/lims.sh", "sample", "add", "--external-id", "S-001", "--specimen-type", "blood", "--container", "TUBE-A"], env)
  run(["./scripts/lims.sh", "snapshot", "export"], env)

  # Ensure snapshot filenames don’t collide (second-level timestamps)
  time.sleep(1.2)

  # Create snapshot #2 (delta +1 sample) in a NEW exclusive container
  run(["./scripts/lims.sh", "container", "add", "--barcode", "TUBE-B", "--kind", "tube"], env)
  run(["./scripts/lims.sh", "sample", "add", "--external-id", "S-002", "--specimen-type", "blood", "--container", "TUBE-B"], env)
  run(["./scripts/lims.sh", "snapshot", "export"], env)

  # diff-latest (N=2 vs latest)
  out = run(["./scripts/lims.sh", "snapshot", "diff-latest", "--n", "2", "--json-only"], env, expect_rc=0)
  rep = parse_first_json_line(out)

  if rep.get("ok") is not True:
    raise SystemExit(f"ERROR: expected ok=true; got: {rep}")

  # snapshot_diff.py schema: rep["deltas"]["counts"] = [{metric, a, b, delta}, ...]
  deltas = rep["deltas"]["counts"]
  metrics = {d.get("metric"): d for d in deltas if isinstance(d, dict)}

  if "samples" not in metrics:
    raise SystemExit(f"ERROR: expected samples delta entry; got: {deltas}")
  if metrics["samples"].get("delta") != 1:
    raise SystemExit(f"ERROR: expected samples delta=+1; got: {metrics['samples']}")

print("OK: snapshot diff-latest regression passed.")
