#!/usr/bin/env python3
import os
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

def run(cmd, env):
    r = subprocess.run(cmd, cwd=REPO, env=env, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        raise SystemExit(f"ERROR: command failed: {cmd}\n{r.stdout}")
    return r.stdout

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    db = td / "lims.sqlite3"
    exports = td / "exports"
    exports.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["DB_PATH"] = str(db)
    env["EXPORTS_DIR"] = str(exports)

    run(["./scripts/lims.sh", "init"], env)
    run(["./scripts/lims.sh", "container", "add", "TUBE-A", "--kind", "tube"], env)
    run(["./scripts/lims.sh", "sample", "add", "S-001", "--container", "TUBE-A"], env)

    out = run(["./scripts/snapshot_export.sh"], env)

    tars = list(exports.glob("snapshot-*.tar.gz"))
    if len(tars) != 1:
        raise SystemExit(f"ERROR: expected exactly 1 tarball, found {len(tars)}")

    snap_dirs = [p for p in exports.iterdir() if p.is_dir() and p.name.startswith("snapshot-")]
    if len(snap_dirs) != 1:
        raise SystemExit(f"ERROR: expected exactly 1 snapshot dir, found {len(snap_dirs)}")

    snap = snap_dirs[0]
    required = ["meta.txt", "lims.sqlite3", "schema.sql", "summary.txt"]
    missing = [f for f in required if not (snap / f).exists()]
    if missing:
        raise SystemExit(f"ERROR: snapshot missing files: {missing}")

print("OK: snapshot_export creates snapshot dir + tarball with expected files.")
