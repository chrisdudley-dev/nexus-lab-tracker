#!/usr/bin/env python3
import json
import os
import subprocess
import tempfile
import time

def run(cmd, env, check=True):
  p = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  if check and p.returncode != 0:
    raise RuntimeError(
      f"Command failed (rc={p.returncode}): {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
    )
  return p

def main() -> int:
  fd, db_path = tempfile.mkstemp(prefix="nexus-lims-sample-report.", suffix=".sqlite")
  os.close(fd)
  env = os.environ.copy()
  env["DB_PATH"] = db_path

  try:
    run(["./scripts/lims.sh", "init"], env)
    run(["./scripts/migrate.sh", "up"], env)

    sfx = str(int(time.time() * 1000))
    c1 = f"TUBE-A-{sfx}"
    c2 = f"TUBE-B-{sfx}"
    sid = f"S-{sfx}"

    run(["./scripts/lims.sh", "container", "add", "--barcode", c1, "--kind", "tube", "--location", "bench-A"], env)
    run(["./scripts/lims.sh", "container", "add", "--barcode", c2, "--kind", "tube", "--location", "bench-B"], env)

    run(["./scripts/lims.sh", "sample", "add", "--external-id", sid, "--specimen-type", "saliva", "--container", c1], env)
    run(["./scripts/lims.sh", "sample", "move", sid, "--to", c2, "--note", "move smoke"], env)
    run(["./scripts/lims.sh", "sample", "status", sid, "--to", "processing", "--note", "status smoke"], env)

    p1 = run(["./scripts/lims.sh", "sample", "report", sid], env, check=False)
    if p1.returncode != 0:
      print("FAIL: sample report should succeed")
      print("STDOUT:\n" + p1.stdout)
      print("STDERR:\n" + p1.stderr)
      return 1

    if "SAMPLE " not in p1.stdout or "EVENTS" not in p1.stdout:
      print("FAIL: expected SAMPLE header and EVENTS section")
      print(p1.stdout)
      return 1

    p2 = run(["./scripts/lims.sh", "sample", "report", sid, "--json"], env, check=False)
    if p2.returncode != 0:
      print("FAIL: sample report --json should succeed")
      print("STDOUT:\n" + p2.stdout)
      print("STDERR:\n" + p2.stderr)
      return 1

    try:
      obj = json.loads(p2.stdout.strip())
    except Exception as e:
      print("FAIL: sample report --json should emit valid JSON")
      print("ERR:", e)
      print("STDOUT:\n" + p2.stdout)
      return 1

    if obj.get("sample", {}).get("external_id") != sid:
      print("FAIL: JSON report sample.external_id mismatch")
      print(obj.get("sample"))
      return 1

    if not isinstance(obj.get("events"), list) or len(obj["events"]) == 0:
      print("FAIL: JSON report should include events list")
      print(obj)
      return 1

    print("OK: sample report emits human + JSON output with expected content.")
    return 0

  finally:
    try:
      os.unlink(db_path)
    except OSError:
      pass

if __name__ == "__main__":
  raise SystemExit(main())
