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
    fd, db_path = tempfile.mkstemp(prefix="nexus-lims-numid.", suffix=".sqlite")
    os.close(fd)
    env = os.environ.copy()
    env["DB_PATH"] = db_path

    try:
        run(["./scripts/lims.sh", "init"], env)

        # Make numeric-looking identifiers (leading zeros), but not likely to collide with small IDs.
        sfx = str(int(time.time() * 1000))[-5:]
        bc  = "0007" + sfx       # numeric-looking barcode
        bc2 = "0008" + sfx
        ext = "12345" + sfx      # numeric-looking external_id

        run(["./scripts/lims.sh", "container", "add", "--barcode", bc, "--kind", "tube"], env)
        run(["./scripts/lims.sh", "sample", "add", "--external-id", ext, "--specimen-type", "blood", "--container", bc], env)

        # container get should succeed even though barcode is numeric-looking
        p1 = run(["./scripts/lims.sh", "container", "get", bc], env, check=False)
        if p1.returncode != 0 or "NOT FOUND" in (p1.stdout + p1.stderr):
            print("ERROR: container get failed for numeric-looking barcode")
            print("STDOUT:\n" + p1.stdout)
            print("STDERR:\n" + p1.stderr)
            return 1

        # sample get should succeed even though external_id is numeric-looking
        p2 = run(["./scripts/lims.sh", "sample", "get", ext], env, check=False)
        if p2.returncode != 0 or "NOT FOUND" in (p2.stdout + p2.stderr):
            print("ERROR: sample get failed for numeric-looking external_id")
            print("STDOUT:\n" + p2.stdout)
            print("STDERR:\n" + p2.stderr)
            return 1

        # sample move should succeed for numeric-looking external_id
        run(["./scripts/lims.sh", "container", "add", "--barcode", bc2, "--kind", "tube"], env)
        p3 = run(["./scripts/lims.sh", "sample", "move", ext, "--to", bc2, "--note", "numid move"], env, check=False)
        if p3.returncode != 0 or "NOT FOUND" in (p3.stdout + p3.stderr):
            print("ERROR: sample move failed for numeric-looking external_id")
            print("STDOUT:\n" + p3.stdout)
            print("STDERR:\n" + p3.stderr)
            return 1

        # sample status should also succeed for numeric-looking external_id
        p4 = run(["./scripts/lims.sh", "sample", "status", ext, "--to", "processing", "--note", "numid status"], env, check=False)
        if p4.returncode != 0 or "NOT FOUND" in (p4.stdout + p4.stderr):
            print("ERROR: sample status failed for numeric-looking external_id")
            print("STDOUT:\n" + p4.stdout)
            print("STDERR:\n" + p4.stderr)
            return 1

        print("OK: numeric-looking identifiers work via id-first fallback across get/move/status.")
        return 0

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
