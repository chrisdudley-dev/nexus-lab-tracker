#!/usr/bin/env python3
import os, subprocess, tempfile

def run(cmd, env, check=True):
    p = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed (rc={p.returncode}): {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return p

def main() -> int:
    fd, db_path = tempfile.mkstemp(prefix="nexus-lims-ws-container.", suffix=".sqlite")
    os.close(fd)
    env = os.environ.copy()
    env["DB_PATH"] = db_path
    try:
        run(["./scripts/lims.sh", "init"], env)

        p1 = run(["./scripts/lims.sh", "sample", "list", "--container", "   "], env, check=False)
        if p1.returncode != 2 or "ERROR:" not in p1.stdout or "NOT FOUND" in p1.stdout:
            print("FAIL: expected whitespace-only --container to be input error (rc=2) for sample list.")
            print("STDOUT:\n" + p1.stdout)
            print("STDERR:\n" + p1.stderr)
            return 1

        p2 = run(["./scripts/lims.sh", "sample", "add", "--specimen-type", "blood", "--container", "   "], env, check=False)
        if p2.returncode != 2 or "ERROR:" not in p2.stdout or "NOT FOUND" in p2.stdout:
            print("FAIL: expected whitespace-only --container to be input error (rc=2) for sample add.")
            print("STDOUT:\n" + p2.stdout)
            print("STDERR:\n" + p2.stderr)
            return 1

        print("OK: whitespace-only --container is rejected as input error (rc=2).")
        return 0
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
