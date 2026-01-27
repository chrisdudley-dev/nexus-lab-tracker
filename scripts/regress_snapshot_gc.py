#!/usr/bin/env python3
import os
import subprocess
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

def run(cmd, env, expect_rc=0):
  r = subprocess.run(cmd, cwd=REPO, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
  if r.returncode != expect_rc:
    raise SystemExit(f"ERROR: rc={r.returncode} (expected {expect_rc}): {cmd}\n--- output ---\n{r.stdout}")
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

  # Create one real snapshot (tar + dir)
  run(["./scripts/lims.sh", "container", "add", "--barcode", "T1", "--kind", "tube"], env)
  run(["./scripts/lims.sh", "sample", "add", "--external-id", "S1", "--specimen-type", "blood", "--container", "T1"], env)
  run(["./scripts/lims.sh", "snapshot", "export"], env)

  tars = sorted(exports.glob("snapshot-*.tar.gz"))
  if len(tars) != 1:
    raise SystemExit(f"ERROR: expected 1 real tarball, found {len(tars)}")
  real_tar = tars[0]
  real_dir = exports / real_tar.name.replace(".tar.gz", "")
  if not real_dir.is_dir():
    raise SystemExit("ERROR: expected matching snapshot dir for real tarball")

  # Create orphan dir (no tar)
  orphan_dir = exports / "snapshot-29990101-000000Z"
  orphan_dir.mkdir(parents=True, exist_ok=True)
  (orphan_dir / "README.txt").write_text("orphan dir", encoding="utf-8")

  # Create orphan tarball (no dir)
  orphan_tar = exports / "snapshot-39990101-000000Z.tar.gz"
  orphan_tar.write_text("not a real tarball", encoding="utf-8")

  # Create pinned orphan tarball (no dir) -> should NEVER delete
  pinned_orphan_tar = exports / "snapshot-49990101-000000Z.tar.gz"
  pinned_orphan_tar.write_text("pinned orphan", encoding="utf-8")
  run(["./scripts/lims.sh", "snapshot", "pin", pinned_orphan_tar.name, "--dir", str(exports)], env)

  # DRY-RUN: should not delete anything
  run(["./scripts/lims.sh", "snapshot", "gc", "--dir", str(exports), "--dry-run"], env)
  assert orphan_dir.exists()
  assert orphan_tar.exists()
  assert pinned_orphan_tar.exists()
  assert real_tar.exists()
  assert real_dir.exists()

  # APPLY: should delete orphan_dir + orphan_tar, keep pinned_orphan_tar and real snapshot artifacts
  run(["./scripts/lims.sh", "snapshot", "gc", "--dir", str(exports), "--apply"], env)
  if orphan_dir.exists():
    raise SystemExit("ERROR: orphan dir was not deleted on apply")
  if orphan_tar.exists():
    raise SystemExit("ERROR: orphan tarball was not deleted on apply")
  if not pinned_orphan_tar.exists():
    raise SystemExit("ERROR: pinned orphan tarball should not be deleted")
  if not real_tar.exists() or not real_dir.exists():
    raise SystemExit("ERROR: real snapshot artifacts should not be deleted")

print("OK: snapshot gc regression passed (dry-run safe; apply deletes orphans; pinned preserved).")
