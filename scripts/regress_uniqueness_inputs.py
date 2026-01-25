#!/usr/bin/env python3
import os, sqlite3, subprocess, tempfile, time

def run(cmd, env, check=True):
    p = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed (rc={p.returncode}): {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return p

def main() -> int:
    fd, db_path = tempfile.mkstemp(prefix="nexus-lims-uniq.", suffix=".sqlite")
    os.close(fd)
    env = os.environ.copy()
    env["DB_PATH"] = db_path

    try:
        run(["./scripts/lims.sh", "init"], env)

        sfx = str(int(time.time() * 1000))
        bc = f"UNIQ-C-{sfx}"
        sid = f"UNIQ-S-{sfx}"

        # Container: create once
        run(["./scripts/lims.sh", "container", "add", "--barcode", bc, "--kind", "tube", "--location", "bench"], env)

        # Duplicate exact should fail
        p = run(["./scripts/lims.sh", "container", "add", "--barcode", bc, "--kind", "tube"], env, check=False)
        if p.returncode == 0:
            print("ERROR: duplicate container barcode unexpectedly succeeded")
            print(p.stdout)
            return 1

        # Whitespace variant should fail (proves normalization)
        p2 = run(["./scripts/lims.sh", "container", "add", "--barcode", bc + "  ", "--kind", "tube"], env, check=False)
        if p2.returncode == 0:
            print("ERROR: whitespace-variant barcode unexpectedly succeeded")
            print(p2.stdout)
            return 1

        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        n_cont = int(cur.execute("SELECT COUNT(*) AS n FROM containers").fetchone()["n"])
        if n_cont != 1:
            print(f"ERROR: expected 1 container, got {n_cont}")
            return 1

        # Sample: create once (explicit external-id)
        run(["./scripts/lims.sh", "sample", "add", "--external-id", sid, "--specimen-type", "blood", "--container", bc], env)

        # Duplicate exact should fail
        p3 = run(["./scripts/lims.sh", "sample", "add", "--external-id", sid, "--specimen-type", "blood"], env, check=False)
        if p3.returncode == 0:
            print("ERROR: duplicate sample external-id unexpectedly succeeded")
            print(p3.stdout)
            return 1

        # Whitespace variant should fail (normalized to same)
        p4 = run(["./scripts/lims.sh", "sample", "add", "--external-id", "  " + sid + "  ", "--specimen-type", "blood"], env, check=False)
        if p4.returncode == 0:
            print("ERROR: whitespace-variant external-id unexpectedly succeeded")
            print(p4.stdout)
            return 1

        # Explicit empty/whitespace external-id should fail
        p5 = run(["./scripts/lims.sh", "sample", "add", "--external-id", "   ", "--specimen-type", "blood"], env, check=False)
        if p5.returncode == 0:
            print("ERROR: whitespace-only external-id unexpectedly succeeded")
            print(p5.stdout)
            return 1

        n_samp = int(cur.execute("SELECT COUNT(*) AS n FROM samples").fetchone()["n"])
        if n_samp != 1:
            print(f"ERROR: expected 1 sample, got {n_samp}")
            return 1

        print("OK: input normalization + uniqueness enforcement behaves as expected.")
        return 0

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
