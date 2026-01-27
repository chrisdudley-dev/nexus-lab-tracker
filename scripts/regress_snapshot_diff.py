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
    raise SystemExit(f"ERROR: rc={r.returncode} (expected {expect_rc}): {cmd}\\n--- output ---\\n{r.stdout}")
  return r.stdout

def parse_first_json_line(out: str):
  for line in out.splitlines():
    line = line.strip()
    if line.startswith("{") and line.endswith("}"):
      return json.loads(line)
  raise ValueError("no JSON line found")

with tempfile.TemporaryDirectory() as td:
  td = Path(td)
  exports_a = td / "exports_a"
  exports_b = td / "exports_b"
  exports_a.mkdir(parents=True, exist_ok=True)
  exports_b.mkdir(parents=True, exist_ok=True)

  db = td / "db.sqlite3"
  env = os.environ.copy()
  env["DB_PATH"] = str(db)

  # Seed + Snapshot A (export to exports_a)
  env["EXPORTS_DIR"] = str(exports_a)
  run(["./scripts/lims.sh", "init"], env)
  run(["./scripts/migrate.sh", "up"], env)
  run(["./scripts/lims.sh", "container", "add", "--barcode", "TUBE-A", "--kind", "tube"], env)
  run(["./scripts/lims.sh", "sample", "add", "--external-id", "S-001", "--specimen-type", "blood", "--container", "TUBE-A"], env)
  run(["./scripts/lims.sh", "snapshot", "export"], env)

  tars_a = sorted(exports_a.glob("snapshot-*.tar.gz"))
  if len(tars_a) != 1:
    raise SystemExit(f"ERROR: expected 1 tarball in exports_a, found {len(tars_a)}")
  A = tars_a[0]

  # Modify DB + Snapshot B (export to exports_b)
  env["EXPORTS_DIR"] = str(exports_b)
  run(["./scripts/lims.sh", "container", "add", "--barcode", "TUBE-B", "--kind", "tube"], env)
  run(["./scripts/lims.sh", "sample", "add", "--external-id", "S-002", "--specimen-type", "blood", "--container", "TUBE-B"], env)
  run(["./scripts/lims.sh", "snapshot", "export"], env)

  tars_b = sorted(exports_b.glob("snapshot-*.tar.gz"))
  if len(tars_b) != 1:
    raise SystemExit(f"ERROR: expected 1 tarball in exports_b, found {len(tars_b)}")
  B = tars_b[0]

  out = run(["./scripts/lims.sh", "snapshot", "diff", str(A), str(B), "--json-only"], env, expect_rc=0)
  rep = parse_first_json_line(out)

  assert rep["ok"] is True
  deltas = rep["deltas"]["counts"]
  metrics = {d["metric"]: d for d in deltas}

  if "samples" not in metrics or metrics["samples"]["delta"] != 1:
    raise SystemExit(f"ERROR: expected samples delta +1, got: {deltas}")
  if "containers" not in metrics or metrics["containers"]["delta"] != 1:
    raise SystemExit(f"ERROR: expected containers delta +1, got: {deltas}")

print("OK: snapshot diff regression passed (detected expected count deltas).")
