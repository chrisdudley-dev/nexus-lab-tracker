#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

def run(cmd, env):
  r = subprocess.run(
    cmd, cwd=REPO, env=env, text=True,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT
  )
  return r.returncode, r.stdout

def parse_first_json_line(out: str):
  for line in out.splitlines():
    line = line.strip()
    if line.startswith("{") and line.endswith("}"):
      return json.loads(line)
  raise ValueError("no JSON line found")

def status_counts_map(rep):
  m = {}
  for row in (rep.get("status_counts", []) or []):
    st = row.get("status")
    ct = row.get("count")
    if st is not None and ct is not None:
      m[st] = int(ct)
  return m

def diff_maps(a: dict, b: dict):
  keys = sorted(set(a.keys()) | set(b.keys()))
  out = []
  for k in keys:
    av = int(a.get(k, 0) or 0)
    bv = int(b.get(k, 0) or 0)
    d = bv - av
    if d != 0:
      out.append({"key": k, "a": av, "b": bv, "delta": d})
  return out

def main():
  ap = argparse.ArgumentParser(prog="snapshot_diff.py")
  ap.add_argument("a", help="artifact A (baseline)")
  ap.add_argument("b", help="artifact B (compare)")
  ap.add_argument("--no-migrate", action="store_true", help="do not apply migrations in temp copies")
  ap.add_argument("--json-only", action="store_true", help="print only JSON diff")
  args = ap.parse_args()

  env = os.environ.copy()

  doctor_cmd = ["./scripts/lims.sh", "snapshot", "doctor", "--json-only"]
  if args.no_migrate:
    doctor_cmd.insert(-1, "--no-migrate")

  # Doctor A
  rc_a, out_a = run(doctor_cmd + [args.a], env)
  rep_a = parse_first_json_line(out_a)
  if rc_a != 0 or not rep_a.get("ok", False):
    print(json.dumps({
      "ok": False,
      "error": "doctor_failed",
      "which": "a",
      "artifact": args.a,
      "doctor": rep_a,
    }, separators=(",", ":")))
    sys.exit(2)

  # Doctor B
  rc_b, out_b = run(doctor_cmd + [args.b], env)
  rep_b = parse_first_json_line(out_b)
  if rc_b != 0 or not rep_b.get("ok", False):
    print(json.dumps({
      "ok": False,
      "error": "doctor_failed",
      "which": "b",
      "artifact": args.b,
      "doctor": rep_b,
    }, separators=(",", ":")))
    sys.exit(2)

  counts_a = rep_a.get("counts", {}) or {}
  counts_b = rep_b.get("counts", {}) or {}

  # Numeric count deltas
  count_keys = sorted(set(counts_a.keys()) | set(counts_b.keys()))
  count_deltas = []
  for k in count_keys:
    try:
      av = int(counts_a.get(k, 0) or 0)
      bv = int(counts_b.get(k, 0) or 0)
    except Exception:
      continue
    d = bv - av
    if d != 0:
      count_deltas.append({"metric": k, "a": av, "b": bv, "delta": d})

  # Status deltas
  st_a = status_counts_map(rep_a)
  st_b = status_counts_map(rep_b)
  status_deltas = diff_maps(st_a, st_b)

  mig_a = (rep_a.get("migrate", {}) or {}).get("status", {}) or {}
  mig_b = (rep_b.get("migrate", {}) or {}).get("status", {}) or {}
  pending_a = mig_a.get("pending", None)
  pending_b = mig_b.get("pending", None)

  audit_a = rep_a.get("container_audit", {}) or {}
  audit_b = rep_b.get("container_audit", {}) or {}

  exc_a = rep_a.get("exclusive_occupied_count")
  exc_b = rep_b.get("exclusive_occupied_count")

  diff = {
    "ok": True,
    "a": {"artifact": rep_a.get("artifact"), "sha256": rep_a.get("work_db_sha256")},
    "b": {"artifact": rep_b.get("artifact"), "sha256": rep_b.get("work_db_sha256")},
    "deltas": {
      "counts": count_deltas,
      "status_counts": status_deltas,
      "migrations_pending": {"a": pending_a, "b": pending_b, "changed": pending_a != pending_b},
      "container_audit": {
        "a_ok": audit_a.get("ok"), "b_ok": audit_b.get("ok"),
        "a_rc": audit_a.get("rc"), "b_rc": audit_b.get("rc"),
        "changed": (audit_a.get("ok"), audit_a.get("rc")) != (audit_b.get("ok"), audit_b.get("rc")),
      },
      "exclusive_occupied_count": {
        "a": exc_a, "b": exc_b,
        "delta": (exc_b - exc_a) if (isinstance(exc_a, int) and isinstance(exc_b, int)) else None,
      }
    }
  }

  print(json.dumps(diff, separators=(",", ":")))

  if not args.json_only:
    print("\n---- Snapshot Diff Summary ----")
    print(f"A: {diff['a']['artifact']}")
    print(f"B: {diff['b']['artifact']}")
    if diff["deltas"]["counts"]:
      print("count deltas:")
      for row in diff["deltas"]["counts"]:
        print(f"  - {row['metric']}: {row['a']} -> {row['b']} (delta {row['delta']:+})")
    if diff["deltas"]["status_counts"]:
      print("status deltas:")
      for row in diff["deltas"]["status_counts"]:
        print(f"  - {row['key']}: {row['a']} -> {row['b']} (delta {row['delta']:+})")
    mig = diff["deltas"]["migrations_pending"]
    if mig["changed"]:
      print(f"migrations_pending changed: {mig['a']} -> {mig['b']}")
    aud = diff["deltas"]["container_audit"]
    if aud["changed"]:
      print(f"container_audit changed: ok {aud['a_ok']} -> {aud['b_ok']}, rc {aud['a_rc']} -> {aud['b_rc']}")
    exc = diff["deltas"]["exclusive_occupied_count"]
    if exc["delta"] not in (None, 0):
      print(f"exclusive_occupied_count: {exc['a']} -> {exc['b']} (delta {exc['delta']:+})")
    if not (diff["deltas"]["counts"] or diff["deltas"]["status_counts"] or mig["changed"] or aud["changed"] or (exc["delta"] not in (None, 0))):
      print("No deltas detected (doctor-reported metrics identical).")
    print("\nRESULT: OK")

  sys.exit(0)

if __name__ == "__main__":
  main()
