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
    fd, db_path = tempfile.mkstemp(prefix="nexus-lims-trim.", suffix=".sqlite")
    os.close(fd)
    env = os.environ.copy()
    env["DB_PATH"] = db_path

    try:
        run(["./scripts/lims.sh", "init"], env)

        sfx = str(int(time.time() * 1000))
        bc = f"TRIM-C-{sfx}"
        sid = f"TRIM-S-{sfx}"

        run(["./scripts/lims.sh", "container", "add", "--barcode", bc, "--kind", "tube", "--location", "bench"], env)
        run(["./scripts/lims.sh", "sample", "add", "--external-id", sid, "--specimen-type", "blood", "--container", bc], env)

        # container get with whitespace
        p1 = run(["./scripts/lims.sh", "container", "get", "  " + bc + "  "], env, check=False)
        if p1.returncode != 0 or "NOT FOUND" in p1.stdout:
            print("ERROR: container get failed with whitespace identifier")
            print(p1.stdout)
            print(p1.stderr)
            return 1

        # sample get with whitespace
        p2 = run(["./scripts/lims.sh", "sample", "get", "  " + sid + "  "], env, check=False)
        if p2.returncode != 0 or "NOT FOUND" in p2.stdout:
            print("ERROR: sample get failed with whitespace identifier")
            print(p2.stdout)
            print(p2.stderr)
            return 1

        # sample status with whitespace (hits resolve_sample_id)
        p3 = run(["./scripts/lims.sh", "sample", "status", "  " + sid + "  ", "--to", "processing", "--note", "trim test"], env, check=False)
        if p3.returncode != 0 or "NOT FOUND" in p3.stdout:
            print("ERROR: sample status failed with whitespace identifier")
            print(p3.stdout)
            print(p3.stderr)
            return 1

        # sample move with whitespace barcode (hits resolve_container_id)
        p4 = run(["./scripts/lims.sh", "sample", "move", sid, "--to", "  " + bc + "  ", "--note", "trim move"], env, check=False)
        if p4.returncode != 0 or "NOT FOUND" in p4.stdout:
            print("ERROR: sample move failed with whitespace container identifier")
            print(p4.stdout)
            print(p4.stderr)
            return 1

        print("OK: identifier trimming for lookup paths behaves as expected.")
        return 0

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
