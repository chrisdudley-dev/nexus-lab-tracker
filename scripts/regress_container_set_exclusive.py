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
    fd, db_path = tempfile.mkstemp(prefix="nexus-lims-set-exclusive.", suffix=".sqlite")
    os.close(fd)
    env = os.environ.copy()
    env["DB_PATH"] = db_path

    try:
        run(["./scripts/lims.sh", "init"], env)
        run(["./scripts/migrate.sh", "up"], env)

        sfx = str(int(time.time() * 1000))
        bag = f"BAG-{sfx}"
        bag2 = f"BAG2-{sfx}"

        run(["./scripts/lims.sh", "container", "add", "--barcode", bag,  "--kind", "bag", "--location", "bench"], env)
        run(["./scripts/lims.sh", "container", "add", "--barcode", bag2, "--kind", "bag", "--location", "bench"], env)

        # bag defaults non-exclusive: allow multiple
        run(["./scripts/lims.sh", "sample", "add", "--external-id", f"S-1-{sfx}", "--specimen-type", "blood", "--container", bag], env)
        run(["./scripts/lims.sh", "sample", "add", "--external-id", f"S-2-{sfx}", "--specimen-type", "blood", "--container", bag], env)

        # turning exclusivity ON with >1 sample must fail
        p = run(["./scripts/lims.sh", "container", "set-exclusive", bag, "on"], env, check=False)
        if p.returncode != 2 or "ERROR:" not in p.stdout:
            print("FAIL: expected rc=2 + ERROR when enabling exclusivity on container with >1 sample")
            print("STDOUT:\n" + p.stdout)
            print("STDERR:\n" + p.stderr)
            return 1

        # bag2: one sample, enable ON should succeed and enforce
        run(["./scripts/lims.sh", "sample", "add", "--external-id", f"S-3-{sfx}", "--specimen-type", "blood", "--container", bag2], env)

        p2 = run(["./scripts/lims.sh", "container", "set-exclusive", bag2, "on"], env, check=False)
        if p2.returncode != 0 or '"is_exclusive": 1' not in p2.stdout:
            print("FAIL: expected enabling exclusivity to succeed and show is_exclusive=1")
            print("STDOUT:\n" + p2.stdout)
            print("STDERR:\n" + p2.stderr)
            return 1

        # second sample into bag2 must now fail (DB trigger + CLI integrity handling)
        p3 = run(["./scripts/lims.sh", "sample", "add", "--external-id", f"S-4-{sfx}", "--specimen-type", "blood", "--container", bag2], env, check=False)
        if p3.returncode != 2 or "ERROR:" not in p3.stdout:
            print("FAIL: expected rc=2 + ERROR when adding second sample into exclusive container")
            print("STDOUT:\n" + p3.stdout)
            print("STDERR:\n" + p3.stderr)
            return 1

        # turn OFF; second sample should succeed now
        p4 = run(["./scripts/lims.sh", "container", "set-exclusive", bag2, "off"], env, check=False)
        if p4.returncode != 0 or '"is_exclusive": 0' not in p4.stdout:
            print("FAIL: expected disabling exclusivity to succeed and show is_exclusive=0")
            print("STDOUT:\n" + p4.stdout)
            print("STDERR:\n" + p4.stderr)
            return 1

        run(["./scripts/lims.sh", "sample", "add", "--external-id", f"S-5-{sfx}", "--specimen-type", "blood", "--container", bag2], env)

        print("OK: container set-exclusive on/off works with guardrails and enforcement.")
        return 0

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
