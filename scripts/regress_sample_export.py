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
  fd, db_path = tempfile.mkstemp(prefix="nexus-lims-sample-export.", suffix=".sqlite")
  os.close(fd)
  env = os.environ.copy()
  env["DB_PATH"] = db_path

  try:
    run(["./scripts/lims.sh", "init"], env)
    run(["./scripts/migrate.sh", "up"], env)

    sfx = str(int(time.time() * 1000))
    c1 = f"TUBE-A-{sfx}"
    sid = f"S-{sfx}"

    run(["./scripts/lims.sh", "container", "add", "--barcode", c1, "--kind", "tube", "--location", "bench-A"], env)
    run(["./scripts/lims.sh", "sample", "add", "--external-id", sid, "--specimen-type", "saliva", "--container", c1], env)

    # JSON
    p1 = run(["./scripts/lims.sh", "sample", "export", sid, "--format", "json"], env, check=False)
    if p1.returncode != 0:
      print("FAIL: sample export --format json should succeed")
      print("STDOUT:\n" + p1.stdout)
      print("STDERR:\n" + p1.stderr)
      return 1

    obj = json.loads(p1.stdout.strip())
    if obj.get("sample", {}).get("external_id") != sid:
      print("FAIL: json export sample.external_id mismatch")
      print(obj.get("sample"))
      return 1
    if "events" not in obj or not isinstance(obj["events"], list):
      print("FAIL: json export missing events list")
      print(obj)
      return 1

    # JSONL
    p2 = run(["./scripts/lims.sh", "sample", "export", sid, "--format", "jsonl"], env, check=False)
    if p2.returncode != 0:
      print("FAIL: sample export --format jsonl should succeed")
      print("STDOUT:\n" + p2.stdout)
      print("STDERR:\n" + p2.stderr)
      return 1

    lines = [ln for ln in p2.stdout.splitlines() if ln.strip()]
    if len(lines) < 1:
      print("FAIL: jsonl export should emit at least 1 line")
      print(p2.stdout)
      return 1

    first = json.loads(lines[0])
    if first.get("type") != "sample":
      print("FAIL: first jsonl line should be type=sample")
      print(first)
      return 1
    if first.get("sample", {}).get("external_id") != sid:
      print("FAIL: jsonl sample.external_id mismatch")
      print(first)
      return 1

    # Invalid format => rc=2
    p3 = run(["./scripts/lims.sh", "sample", "export", sid, "--format", "nope"], env, check=False)
    if p3.returncode != 2:
      print("FAIL: invalid --format should return rc=2")
      print("rc=", p3.returncode)
      print("STDOUT:\n" + p3.stdout)
      print("STDERR:\n" + p3.stderr)
      return 1

    print("OK: sample export supports json + jsonl and rejects invalid --format.")
    return 0

  finally:
    try:
      os.unlink(db_path)
    except OSError:
      pass

if __name__ == "__main__":
  raise SystemExit(main())
