#!/usr/bin/env python3
import os, subprocess, tempfile, time

def run(cmd, env, check=True):
    p = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed (rc={p.returncode}): {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return p

def main() -> int:
    fd, db_path = tempfile.mkstemp(prefix="nexus-lims-container-show.", suffix=".sqlite")
    os.close(fd)
    env = os.environ.copy()
    env["DB_PATH"] = db_path

    try:
        run(["./scripts/lims.sh", "init"], env)
        run(["./scripts/migrate.sh", "up"], env)

        sfx = str(int(time.time() * 1000))
        bag = f"BAG-{sfx}"
        sid = f"S-{sfx}"

        run(["./scripts/lims.sh", "container", "add", "--barcode", bag, "--kind", "bag", "--location", "bench"], env)
        run(["./scripts/lims.sh", "sample", "add", "--external-id", sid, "--specimen-type", "blood", "--container", bag], env)

        p1 = run(["./scripts/lims.sh", "container", "show", bag], env, check=False)
        if p1.returncode != 0:
            print("FAIL: container show should succeed")
            print("STDOUT:\n" + p1.stdout)
            print("STDERR:\n" + p1.stderr)
            return 1
        if '"occupancy_count": 1' not in p1.stdout or sid not in p1.stdout:
            print("FAIL: expected occupancy_count=1 and sample external_id to appear in output")
            print("STDOUT:\n" + p1.stdout)
            print("STDERR:\n" + p1.stderr)
            return 1

        p2 = run(["./scripts/lims.sh", "container", "show", "NOPE-DOES-NOT-EXIST"], env, check=False)
        if p2.returncode != 2 or "NOT FOUND" not in p2.stdout:
            print("FAIL: expected NOT FOUND with rc=2 for unknown container")
            print("STDOUT:\n" + p2.stdout)
            print("STDERR:\n" + p2.stderr)
            return 1

        print("OK: container show includes occupancy_count and samples; NOT FOUND behaves correctly.")
        return 0

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
