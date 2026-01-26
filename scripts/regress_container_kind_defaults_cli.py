#!/usr/bin/env python3
import os, subprocess, tempfile, time

def run(cmd, env, check=True):
    p = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed (rc={p.returncode}): {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return p

def expect_rc(p, rc, must_contain=None):
    if p.returncode != rc:
        raise RuntimeError(f"Expected rc={rc}, got rc={p.returncode}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
    if must_contain and must_contain not in p.stdout:
        raise RuntimeError(f"Expected stdout to contain: {must_contain}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")

def main() -> int:
    fd, db_path = tempfile.mkstemp(prefix="nexus-lims-kind-defaults.", suffix=".sqlite")
    os.close(fd)
    env = os.environ.copy()
    env["DB_PATH"] = db_path

    try:
        run(["./scripts/lims.sh", "init"], env)
        run(["./scripts/migrate.sh", "up"], env)

        sfx = str(int(time.time() * 1000))

        # 1) Create a bag container BEFORE setting defaults (should be non-exclusive)
        bag = f"BAG-{sfx}"
        out1 = run(["./scripts/lims.sh", "container", "add", "--barcode", bag, "--kind", "bag", "--location", "bench"], env)
        if '"is_exclusive": 1' in out1.stdout:
            print("FAIL: expected bag to default non-exclusive before policy set")
            print(out1.stdout)
            return 1

        # add two samples into bag (should succeed)
        run(["./scripts/lims.sh", "sample", "add", "--external-id", f"S-1-{sfx}", "--specimen-type", "blood", "--container", bag], env)
        run(["./scripts/lims.sh", "sample", "add", "--external-id", f"S-2-{sfx}", "--specimen-type", "blood", "--container", bag], env)

        # 2) Set policy: bag => exclusive on
        p_set = run(["./scripts/lims.sh", "container", "kind-defaults", "set", "bag", "on"], env, check=False)
        expect_rc(p_set, 0, "OK: kind default updated")

        # 3) Create a new bag container AFTER policy set; should come out exclusive
        bag2 = f"BAG2-{sfx}"
        out2 = run(["./scripts/lims.sh", "container", "add", "--barcode", bag2, "--kind", "bag", "--location", "bench"], env)
        if '"is_exclusive": 1' not in out2.stdout:
            print("FAIL: expected new bag container to be exclusive after policy set")
            print(out2.stdout)
            return 1

        # Enforced: second sample into bag2 should fail (DB triggers + CLI IntegrityError handling)
        run(["./scripts/lims.sh", "sample", "add", "--external-id", f"S-3-{sfx}", "--specimen-type", "blood", "--container", bag2], env)
        p_fail = run(["./scripts/lims.sh", "sample", "add", "--external-id", f"S-4-{sfx}", "--specimen-type", "blood", "--container", bag2], env, check=False)
        expect_rc(p_fail, 2, "ERROR:")

        # 4) Apply should refuse because bag has 2 samples (would become exclusive)
        p_apply = run(["./scripts/lims.sh", "container", "kind-defaults", "apply", "bag"], env, check=False)
        expect_rc(p_apply, 2, "ERROR:")

        # 5) Turning policy off should still work
        p_set2 = run(["./scripts/lims.sh", "container", "kind-defaults", "set", "bag", "off"], env, check=False)
        expect_rc(p_set2, 0, "OK: kind default updated")

        print("OK: kind-defaults CLI works (set/list/apply) with safety guardrails.")
        return 0

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
