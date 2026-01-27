#!/usr/bin/env python3
import json
import os
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

def run(cmd, env, expect_rc=0):
  r = subprocess.run(
    cmd,
    cwd=REPO,
    env=env,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
  )
  if r.returncode != expect_rc:
    raise SystemExit(
      f"ERROR: command rc={r.returncode} (expected {expect_rc}): {cmd}\n"
      f"--- output ---\n{r.stdout}"
    )
  return r.stdout

def first_json_line(output: str):
  for line in output.splitlines():
    line = line.strip()
    if not line:
      continue
    if line.startswith("{") and line.endswith("}"):
      return json.loads(line)
  raise ValueError(f"no JSON line found in output:\n{output}")

with tempfile.TemporaryDirectory() as td:
  td = Path(td)
  exports = td / "exports"
  exports.mkdir(parents=True, exist_ok=True)

  db1 = td / "db1.sqlite3"
  env1 = os.environ.copy()
  env1["DB_PATH"] = str(db1)
  env1["EXPORTS_DIR"] = str(exports)

  # Seed a snapshot with real events
  run(["./scripts/lims.sh", "init"], env1)
  run(["./scripts/migrate.sh", "up"], env1)

  run(["./scripts/lims.sh", "container", "add", "--barcode", "TUBE-A", "--kind", "tube"], env1)
  run(["./scripts/lims.sh", "container", "add", "--barcode", "TUBE-B", "--kind", "tube"], env1)

  run(["./scripts/lims.sh", "sample", "add", "--external-id", "S-001", "--specimen-type", "blood", "--container", "TUBE-A"], env1)
  run(["./scripts/lims.sh", "sample", "status", "S-001", "--to", "processing", "--note", "start"], env1)
  run(["./scripts/lims.sh", "sample", "move", "S-001", "--to", "TUBE-B", "--note", "move"], env1)
  run(["./scripts/lims.sh", "sample", "status", "S-001", "--to", "analyzing", "--note", "analyze"], env1)
  run(["./scripts/lims.sh", "sample", "status", "S-001", "--to", "completed", "--note", "done"], env1)

  run(["./scripts/lims.sh", "snapshot", "export"], env1)

  tars = list(exports.glob("snapshot-*.tar.gz"))
  if len(tars) != 1:
    raise SystemExit(f"ERROR: expected exactly 1 tarball, found {len(tars)}")
  tarball = tars[0]

  # Target DB (exists) to test overwrite guardrails
  db2 = td / "db2.sqlite3"
  env2 = os.environ.copy()
  env2["DB_PATH"] = str(db2)
  env2["EXPORTS_DIR"] = str(exports)

  run(["./scripts/lims.sh", "init"], env2)
  run(["./scripts/migrate.sh", "up"], env2)

  out = run(["./scripts/lims.sh", "snapshot", "restore", str(tarball)], env2, expect_rc=2)
  if "ERROR: target DB already exists" not in out:
    raise SystemExit(f"ERROR: expected overwrite refusal message, got:\n{out}")

  out2 = run(["./scripts/lims.sh", "snapshot", "restore", str(tarball), "--force", "--backup"], env2)
  # backup file should exist
  backups = sorted(td.glob("db2.sqlite3.bak-*"))
  if not backups:
    raise SystemExit("ERROR: expected a backup db2.sqlite3.bak-* but found none")

  # Verify sample exists and status preserved
  got = run(["./scripts/lims.sh", "sample", "get", "S-001"], env2)
  row = first_json_line(got)
  if row.get("external_id") != "S-001":
    raise SystemExit(f"ERROR: expected external_id S-001, got {row.get('external_id')}")
  if row.get("status") != "completed":
    raise SystemExit(f"ERROR: expected status completed, got {row.get('status')}")

  ev = run(["./scripts/lims.sh", "sample", "events", "S-001", "--limit", "10"], env2)
  if "event_type" not in ev:
    raise SystemExit(f"ERROR: expected events output to include event_type, got:\n{ev}")

print("OK: snapshot restore round-trip works (guardrails + backup + migrated + data preserved).")
