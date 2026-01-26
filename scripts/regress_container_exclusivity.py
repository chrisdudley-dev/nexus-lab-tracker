#!/usr/bin/env python3
import os, subprocess, tempfile, time

def run(cmd, env, check=True):
    p = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed (rc={p.returncode}): {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return p

def must_ok(p):
    if p.returncode != 0:
        raise RuntimeError(f"Expected rc=0. rc={p.returncode}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")

def must_err(p):
    if p.returncode != 2 or "ERROR:" not in p.stdout:
        raise RuntimeError(f"Expected rc=2 with ERROR:. rc={p.returncode}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")

def main() -> int:
    fd, db_path = tempfile.mkstemp(prefix="nexus-lims-exclusive.", suffix=".sqlite")
    os.close(fd)
    env = os.environ.copy()
    env["DB_PATH"] = db_path

    try:
        must_ok(run(["./scripts/lims.sh", "init"], env))
        must_ok(run(["./scripts/migrate.sh", "up"], env))

        sfx = str(int(time.time() * 1000))
        tube  = f"TUBE-{sfx}"
        tube2 = f"TUBE2-{sfx}"
        vial  = f"VIAL-{sfx}"
        plate = f"PLATE-{sfx}"
        bag   = f"BAG-{sfx}"

        must_ok(run(["./scripts/lims.sh", "container", "add", "--barcode", tube,  "--kind", "tube",  "--location", "bench"], env))
        must_ok(run(["./scripts/lims.sh", "container", "add", "--barcode", tube2, "--kind", "tube",  "--location", "bench"], env))
        must_ok(run(["./scripts/lims.sh", "container", "add", "--barcode", vial,  "--kind", "vial",  "--location", "bench"], env))
        must_ok(run(["./scripts/lims.sh", "container", "add", "--barcode", plate, "--kind", "plate", "--location", "bench"], env))
        must_ok(run(["./scripts/lims.sh", "container", "add", "--barcode", bag,  "--kind", "bag",  "--location", "bench"], env))

        # tube exclusive by default: second sample into same tube should fail
        sid1 = f"S-1-{sfx}"
        sid2 = f"S-2-{sfx}"
        must_ok(run(["./scripts/lims.sh", "sample", "add", "--external-id", sid1, "--specimen-type", "blood", "--container", tube], env))

        p = run(["./scripts/lims.sh", "sample", "add", "--external-id", sid2, "--specimen-type", "blood", "--container", tube], env, check=False)
        must_err(p)

        # move sid1 to tube2; tube becomes free; sid2 into tube should succeed
        must_ok(run(["./scripts/lims.sh", "sample", "move", sid1, "--to", tube2], env))
        must_ok(run(["./scripts/lims.sh", "sample", "add", "--external-id", sid2, "--specimen-type", "blood", "--container", tube], env))

        # vial exclusive by default too
        sid3 = f"S-3-{sfx}"
        sid4 = f"S-4-{sfx}"
        must_ok(run(["./scripts/lims.sh", "sample", "add", "--external-id", sid3, "--specimen-type", "blood", "--container", vial], env))
        p2 = run(["./scripts/lims.sh", "sample", "add", "--external-id", sid4, "--specimen-type", "blood", "--container", vial], env, check=False)
        must_err(p2)

        # plate non-exclusive: allow multiple
        sid5 = f"S-5-{sfx}"
        sid6 = f"S-6-{sfx}"
        must_ok(run(["./scripts/lims.sh", "sample", "add", "--external-id", sid5, "--specimen-type", "blood", "--container", plate], env))
        must_ok(run(["./scripts/lims.sh", "sample", "add", "--external-id", sid6, "--specimen-type", "blood", "--container", plate], env))

        # bag (unknown kind) defaults non-exclusive: allow multiple
        sid7 = f"S-7-{sfx}"
        sid8 = f"S-8-{sfx}"
        must_ok(run(["./scripts/lims.sh", "sample", "add", "--external-id", sid7, "--specimen-type", "blood", "--container", bag], env))
        must_ok(run(["./scripts/lims.sh", "sample", "add", "--external-id", sid8, "--specimen-type", "blood", "--container", bag], env))

        print("OK: kind-defaults apply: tube/vial exclusive; plate/bag non-exclusive.")
        return 0

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
