#!/usr/bin/env python3
import os, subprocess, tempfile, shutil, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

def run(cmd, check=True, env=None):
    p = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"FAIL cmd: {' '.join(cmd)}\n"
            f"rc={p.returncode}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return p

def main():
    tmp = Path(tempfile.mkdtemp(prefix="nexus_tar_unsafe_"))
    try:
        env = os.environ.copy()
        env["DB_PATH"] = str(tmp / "lims.sqlite3")

        # Build a tarball that contains lims.sqlite3 AND a symlink (should be rejected early).
        w = tmp / "work"
        w.mkdir()
        (w / "lims.sqlite3").write_text("not-a-sqlite-db", encoding="utf-8")
        os.symlink("../../etc/passwd", w / "evil_link")

        bad = tmp / "bad_snapshot.tgz"
        run(["tar", "-czf", str(bad), "-C", str(w), "."], env=env)

        r1 = run(["./scripts/snapshot_restore.sh", str(bad)], check=False, env=env)
        if r1.returncode == 0:
            sys.stderr.write("FAIL: restore accepted tarball containing symlink\n")
            sys.stderr.write(r1.stdout + "\n" + r1.stderr + "\n")
            raise SystemExit(2)

        r2 = run(["./scripts/snapshot_verify.sh", str(bad)], check=False, env=env)
        if r2.returncode == 0:
            sys.stderr.write("FAIL: verify accepted tarball containing symlink\n")
            sys.stderr.write(r2.stdout + "\n" + r2.stderr + "\n")
            raise SystemExit(2)

        print(f"OK: unsafe tar entries rejected (restore rc={r1.returncode}, verify rc={r2.returncode}).")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    main()
