#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

def eprint(*a):
  print(*a, file=sys.stderr)

def sha256_file(p: Path) -> str:
  h = hashlib.sha256()
  with p.open("rb") as f:
    for chunk in iter(lambda: f.read(1024 * 1024), b""):
      h.update(chunk)
  return h.hexdigest()

def parse_multiline_json(text: str):
  s = text.find("{")
  e = text.rfind("}")
  if s == -1 or e == -1 or e < s:
    return None
  return json.loads(text[s:e+1])

def _safe_extractall(tf: tarfile.TarFile, dest: Path) -> None:
  dest_r = dest.resolve()
  for mem in tf.getmembers():
    name = mem.name
    # Basic path traversal guards
    if name.startswith(("/", "\\")):
      raise ValueError(f"unsafe tar member path (absolute): {name}")
    parts = Path(name).parts
    if ".." in parts:
      raise ValueError(f"unsafe tar member path (..): {name}")
    out = (dest_r / name).resolve()
    try:
      out.relative_to(dest_r)
    except Exception:
      raise ValueError(f"unsafe tar member path (escapes dest): {name}")
  tf.extractall(path=dest_r)

def resolve_snapshot_context(artifact: Path, tmp: Path):
  """
  Returns (src_db, snap_dir, tarball_path)
    - src_db: path to lims.sqlite3
    - snap_dir: directory containing lims.sqlite3 (may be None for direct sqlite3 artifacts)
    - tarball_path: original tarball path if artifact is tarball else None
  """
  if artifact.is_dir():
    direct = artifact / "lims.sqlite3"
    if direct.exists():
      return direct, artifact, None
    found = sorted(artifact.glob("**/lims.sqlite3"))
    found = [pp for pp in found if len(pp.relative_to(artifact).parts) <= 3]
    if len(found) == 1:
      return found[0], found[0].parent, None
    if len(found) == 0:
      raise ValueError("no lims.sqlite3 found in directory artifact")
    raise ValueError("multiple lims.sqlite3 found in directory artifact (ambiguous)")

  if artifact.is_file():
    name = artifact.name
    if name.endswith((".tar.gz", ".tgz")):
      extract_root = tmp / "snapshot_extract"
      extract_root.mkdir(parents=True, exist_ok=True)
      with tarfile.open(artifact, "r:gz") as tf:
        _safe_extractall(tf, extract_root)
      found = sorted(extract_root.rglob("lims.sqlite3"))
      if len(found) != 1:
        raise ValueError(f"expected exactly 1 lims.sqlite3 in tarball, found {len(found)}")
      src_db = found[0].resolve()
      return src_db, src_db.parent, artifact

    if name.endswith(".sqlite3") or name == "lims.sqlite3":
      return artifact, None, None

  raise ValueError("unsupported artifact type; pass snapshot dir, snapshot-*.tar.gz, or lims.sqlite3")
def table_exists(conn: sqlite3.Connection, table: str) -> bool:
  cur = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,))
  return cur.fetchone() is not None

def get_column_names(conn: sqlite3.Connection, table: str):
  cur = conn.execute(f"PRAGMA table_info({table})")
  return [r[1] for r in cur.fetchall()]

def run(cmd, env, expect_rc=None):
  r = subprocess.run(
    cmd, cwd=REPO, env=env, text=True,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT
  )
  if expect_rc is not None and r.returncode != expect_rc:
    raise RuntimeError(f"rc={r.returncode} expected {expect_rc}\nCMD: {cmd}\nOUTPUT:\n{r.stdout}")
  return r.returncode, r.stdout

def main():
  ap = argparse.ArgumentParser(prog="snapshot_doctor.py")
  ap.add_argument("artifact", help="snapshot dir, snapshot-*.tar.gz, or lims.sqlite3")
  ap.add_argument("--no-migrate", action="store_true", help="do not apply migrations in temp copy")
  ap.add_argument("--json-only", action="store_true", help="print only JSON report")
  ap.add_argument("--max-audit-lines", type=int, default=60, help="max audit lines in report")
  args = ap.parse_args()

  artifact = Path(args.artifact)
  if not artifact.is_absolute():
    artifact = (REPO / artifact).resolve()

  report = {
    "ok": False,
    "artifact": str(artifact),
    "resolved_snapshot_db": None,
    "work_db": None,
    "work_db_sha256": None,
    "work_db_size_bytes": None,
    "integrity_ok": None,
    "foreign_key_violations": None,
    "migrate": {"attempted": (not args.no_migrate), "status": None},
    "counts": {},
    "status_counts": [],
    "exclusive_occupied_count": None,
    "container_audit": {"rc": None, "ok": None, "excerpt": []},
    "notes": [],
  }

  with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    try:
      src_db, snap_dir, tarball_path = resolve_snapshot_context(artifact, td)
    except Exception as ex:
      report["notes"].append(f"artifact_resolution_error: {ex}")
      print(json.dumps(report, separators=(",", ":")))
      sys.exit(2)

    report["resolved_snapshot_db"] = str(src_db)

    report["resolved_snapshot_dir"] = (str(snap_dir) if snap_dir is not None else None)
    report["resolved_tarball"] = (str(tarball_path) if tarball_path is not None else None)

    # Validate manifest (if present). Uses portable validator to support extracted tarballs / moved dirs.
    validator = REPO / "scripts" / "snapshot_validate_manifest.py"
    if snap_dir is not None and validator.exists():
      cmd = [sys.executable, str(validator), "--snap-dir", str(snap_dir), "--check-included"]
      if tarball_path is not None:
        cmd += ["--tarball", str(tarball_path)]
      r = subprocess.run(cmd, cwd=REPO, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      if r.returncode != 0:
        msg = (r.stderr.strip() or r.stdout.strip() or f"rc={r.returncode}")
        raise RuntimeError(f"manifest_validation_failed: {msg}")

    work_db = td / "doctor.sqlite3"
    shutil.copy2(src_db, work_db)
    try:
      os.chmod(work_db, 0o600)
    except Exception:
      pass

    report["work_db"] = str(work_db)
    report["work_db_size_bytes"] = work_db.stat().st_size
    report["work_db_sha256"] = sha256_file(work_db)

    # Open DB
    try:
      conn = sqlite3.connect(str(work_db))
    except Exception as ex:
      report["notes"].append(f"sqlite_open_error: {ex}")
      print(json.dumps(report, separators=(",", ":")))
      sys.exit(2)

    # integrity_check
    try:
      rows = conn.execute("PRAGMA integrity_check").fetchall()
      integrity_last = rows[-1][0] if rows else None
      report["integrity_ok"] = (integrity_last == "ok")
    except Exception as ex:
      report["notes"].append(f"integrity_check_error: {ex}")
      report["integrity_ok"] = False

    # foreign_key_check
    try:
      conn.execute("PRAGMA foreign_keys=ON")
      fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
      report["foreign_key_violations"] = len(fk_rows)
      if fk_rows:
        # include a tiny sample in notes (not the whole thing)
        report["notes"].append(f"foreign_key_violation_sample: {fk_rows[:3]}")
    except Exception as ex:
      report["notes"].append(f"foreign_key_check_error: {ex}")
      report["foreign_key_violations"] = None

    # Optionally migrate forward (temp only)
    env = os.environ.copy()
    env["DB_PATH"] = str(work_db)

    if not args.no_migrate:
      rc_up, out_up = run(["./scripts/migrate.sh", "up"], env)
      if rc_up != 0:
        report["notes"].append("migrate_up_failed")
        report["notes"].append(out_up.strip().splitlines()[-20:])
      rc_st, out_st = run(["./scripts/migrate.sh", "status"], env)
      st = parse_multiline_json(out_st) if out_st else None
      report["migrate"]["status"] = st
    else:
      rc_st, out_st = run(["./scripts/migrate.sh", "status"], env)
      st = parse_multiline_json(out_st) if out_st else None
      report["migrate"]["status"] = st

    # Counts + status counts
    try:
      if table_exists(conn, "samples"):
        report["counts"]["samples"] = conn.execute("SELECT COUNT(1) FROM samples").fetchone()[0]
        if "status" in get_column_names(conn, "samples"):
          rows = conn.execute("SELECT status, COUNT(1) FROM samples GROUP BY status ORDER BY status").fetchall()
          report["status_counts"] = [{"status": r[0], "count": r[1]} for r in rows]
      if table_exists(conn, "containers"):
        report["counts"]["containers"] = conn.execute("SELECT COUNT(1) FROM containers").fetchone()[0]
      if table_exists(conn, "sample_events"):
        report["counts"]["sample_events"] = conn.execute("SELECT COUNT(1) FROM sample_events").fetchone()[0]
      if table_exists(conn, "audit_events"):
        report["counts"]["audit_events"] = conn.execute("SELECT COUNT(1) FROM audit_events").fetchone()[0]
    except Exception as ex:
      report["notes"].append(f"count_query_error: {ex}")

    # Optional drift signal: count occupied exclusive containers (best-effort)
    try:
      if table_exists(conn, "containers") and table_exists(conn, "samples"):
        ccols = get_column_names(conn, "containers")
        scols = get_column_names(conn, "samples")
        ex_col = None
        for cand in ("is_exclusive", "exclusive"):
          if cand in ccols:
            ex_col = cand
            break
        if ex_col and ("container_id" in scols):
          q = f"""
            SELECT COUNT(1)
            FROM containers c
            WHERE c.{ex_col}=1
              AND EXISTS (SELECT 1 FROM samples s WHERE s.container_id=c.id)
          """
          report["exclusive_occupied_count"] = conn.execute(q).fetchone()[0]
    except Exception as ex:
      report["notes"].append(f"exclusive_occupied_query_error: {ex}")

    conn.close()

    # Container audit via CLI (uses DB_PATH temp)
    rc_a, out_a = run(["./scripts/lims.sh", "container", "audit"], env)
    excerpt = out_a.strip().splitlines()[:max(0, args.max_audit_lines)]
    report["container_audit"]["rc"] = rc_a
    report["container_audit"]["ok"] = (rc_a == 0)
    report["container_audit"]["excerpt"] = excerpt

    # Determine OK / FAIL
    pending = None
    st = report["migrate"]["status"]
    if isinstance(st, dict):
      pending = st.get("pending", None)

    ok = True
    if report["integrity_ok"] is not True:
      ok = False
    if report["foreign_key_violations"] not in (0, None):
      ok = False
    if pending not in ([], None):
      ok = False
    if report["container_audit"]["ok"] is not True:
      ok = False

    report["ok"] = ok

    # Print JSON first (machine-friendly)
    print(json.dumps(report, separators=(",", ":")))

    if not args.json_only:
      print("\n---- Snapshot Doctor Summary ----")
      print(f"artifact: {report['artifact']}")
      print(f"snapshot_db: {report['resolved_snapshot_db']}")
      print(f"work_db_sha256: {report['work_db_sha256']}")
      print(f"integrity_ok: {report['integrity_ok']}")
      print(f"foreign_key_violations: {report['foreign_key_violations']}")
      if isinstance(st, dict):
        print(f"migrations_pending: {st.get('pending')}")
      print(f"container_audit_rc: {report['container_audit']['rc']}")
      print(f"counts: {report.get('counts', {})}")
      if report["status_counts"]:
        print("status_counts:")
        for row in report["status_counts"]:
          print(f"  - {row['status']}: {row['count']}")
      if report["exclusive_occupied_count"] is not None:
        print(f"exclusive_occupied_count: {report['exclusive_occupied_count']}")
      if report["notes"]:
        print("notes:")
        for n in report["notes"][:10]:
          print(f"  - {n}")
      print(f"\nRESULT: {'OK' if report['ok'] else 'FAIL'}")

    sys.exit(0 if report["ok"] else 2)

if __name__ == "__main__":
  main()
