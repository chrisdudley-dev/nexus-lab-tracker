#!/usr/bin/env python3
import os, subprocess, tempfile, time, sqlite3

def run(cmd, env, check=True):
    p = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed (rc={p.returncode}): {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return p

def main() -> int:
    fd, db_path = tempfile.mkstemp(prefix="nexus-lims-container-audit.", suffix=".sqlite")
    os.close(fd)
    env = os.environ.copy()
    env["DB_PATH"] = db_path

    try:
        run(["./scripts/lims.sh", "init"], env)
        run(["./scripts/migrate.sh", "up"], env)

        # Fresh DB should audit clean
        p0 = run(["./scripts/lims.sh", "container", "audit"], env, check=False)
        if p0.returncode != 0 or "OK: audit found no hard issues" not in p0.stdout:
            print("FAIL: expected clean audit on fresh DB")
            print("STDOUT:\n" + p0.stdout)
            print("STDERR:\n" + p0.stderr)
            return 1

        sfx = str(int(time.time() * 1000))

        # Create a bag container (non-exclusive by default) and insert 2 samples.
        bag = f"BAG-{sfx}"
        run(["./scripts/lims.sh", "container", "add", "--barcode", bag, "--kind", "bag", "--location", "bench"], env)
        run(["./scripts/lims.sh", "sample", "add", "--external-id", f"S-1-{sfx}", "--specimen-type", "blood", "--container", bag], env)
        run(["./scripts/lims.sh", "sample", "add", "--external-id", f"S-2-{sfx}", "--specimen-type", "blood", "--container", bag], env)

        # Guardrail should prevent enabling exclusivity via CLI when container holds >1 sample.
        p_guard = run(["./scripts/lims.sh", "container", "set-exclusive", bag, "on"], env, check=False)
        if p_guard.returncode != 2 or "ERROR:" not in p_guard.stdout:
            print("FAIL: expected CLI guardrail to reject set-exclusive on with >1 sample")
            print("STDOUT:\n" + p_guard.stdout)
            print("STDERR:\n" + p_guard.stderr)
            return 1

        # Bypass CLI (intentional corruption): flip is_exclusive directly in DB.
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE containers SET is_exclusive = 1 WHERE barcode = ?", (bag,))
        conn.commit()
        conn.close()

        # Now audit must fail (hard issue: exclusive container with occupancy > 1).
        p1 = run(["./scripts/lims.sh", "container", "audit"], env, check=False)
        if p1.returncode != 2 or "ERROR: audit found" not in p1.stdout:
            print("FAIL: expected audit to report hard issues (exclusive occupancy violation)")
            print("STDOUT:\n" + p1.stdout)
            print("STDERR:\n" + p1.stderr)
            return 1

        print("OK: container audit detects hard issues and returns rc=2.")
        return 0

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
