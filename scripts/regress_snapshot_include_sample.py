#!/usr/bin/env python3
import json
import os
import subprocess
import tempfile
from pathlib import Path

def run(cmd, env, check=True):
  p = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  if check and p.returncode != 0:
    raise RuntimeError(
      f"Command failed (rc={p.returncode}): {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
    )
  return p

def main() -> int:
  tmp = Path(tempfile.mkdtemp(prefix="nexus-lims-snap-inc."))
  db_path = tmp / "lims.sqlite3"
  exports_dir = tmp / "exports"
  exports_dir.mkdir(parents=True, exist_ok=True)

  env = os.environ.copy()
  env["DB_PATH"] = str(db_path)

  run(["./scripts/lims.sh", "init"], env)
  run(["./scripts/migrate.sh", "up"], env)

  run(["./scripts/lims.sh", "container", "add", "--barcode", "TUBE-1", "--kind", "tube", "--location", "bench-A"], env)
  run(["./scripts/lims.sh", "container", "add", "--barcode", "TUBE-2", "--kind", "tube", "--location", "bench-A"], env)
  run(["./scripts/lims.sh", "sample", "add", "--external-id", "S-001", "--specimen-type", "saliva", "--container", "TUBE-1"], env)
  run(["./scripts/lims.sh", "sample", "add", "--external-id", "S-002", "--specimen-type", "blood", "--container", "TUBE-2"], env)

  p = run(
    ["./scripts/lims.sh", "snapshot", "export", "--exports-dir", str(exports_dir), "--include-sample", "S-001", "--include-sample", "S-002"],
    env,
    check=False,
  )
  if p.returncode != 0:
    print("FAIL: snapshot export with --include-sample should succeed")
    print("STDOUT:\n" + p.stdout)
    print("STDERR:\n" + p.stderr)
    return 1

  snaps = sorted([d for d in exports_dir.iterdir() if d.is_dir() and d.name.startswith("snapshot-")], key=lambda d: d.name)
  if not snaps:
    print("FAIL: no snapshot-* directory created")
    return 1
  snap = snaps[-1]

  exp_file = snap / "exports" / "samples" / "sample-S-001.json"
  exp_file2 = snap / "exports" / "samples" / "sample-S-002.json"
  if not exp_file.exists():

  if not exp_file2.exists():
    print("FAIL: missing included sample export:", exp_file2)
    return 1

    print("FAIL: missing included sample export:", exp_file)
    return 1

  # Enforce stable filenames: legacy underscore variant must NOT be produced
  exp_file_alt = snap / "exports" / "samples" / "sample-S-001_.json"
  if exp_file_alt.exists():
    print("FAIL: legacy underscore filename still produced:", exp_file_alt)
    return 1

  obj = json.loads(exp_file.read_text(encoding="utf-8"))
  if obj.get("sample", {}).get("external_id") != "S-001":
    print("FAIL: included export JSON external_id mismatch")
    print(obj.get("sample"))
    return 1

  print("OK: snapshot includes sample export JSON.")
  return 0

if __name__ == "__main__":
  raise SystemExit(main())
