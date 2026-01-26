#!/usr/bin/env python3
import os, subprocess, tempfile, time

def run(cmd, env, check=True):
    p = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed (rc={p.returncode}): {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return p

def must_no_results(p):
    if p.returncode != 0 or "(no results)" not in p.stdout:
        raise RuntimeError(
            f"Expected rc=0 with (no results). rc={p.returncode}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )

def must_limit_error(p):
    if p.returncode != 2 or "ERROR:" not in p.stdout:
        raise RuntimeError(
            f"Expected rc=2 with ERROR. rc={p.returncode}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )

def main() -> int:
    fd, db_path = tempfile.mkstemp(prefix="nexus-lims-limit.", suffix=".sqlite")
    os.close(fd)
    env = os.environ.copy()
    env["DB_PATH"] = db_path

    try:
        run(["./scripts/lims.sh", "init"], env)

        sfx = str(int(time.time() * 1000))
        bc = f"LIM-C-{sfx}"
        sid = f"LIM-S-{sfx}"

        run(["./scripts/lims.sh", "container", "add", "--barcode", bc, "--kind", "tube", "--location", "bench"], env)
        run(["./scripts/lims.sh", "sample", "add", "--external-id", sid, "--specimen-type", "blood", "--container", bc], env)

        must_no_results(run(["./scripts/lims.sh", "container", "list", "--limit", "0"], env, check=False))
        must_no_results(run(["./scripts/lims.sh", "sample", "list", "--limit", "0"], env, check=False))
        must_no_results(run(["./scripts/lims.sh", "sample", "events", sid, "--limit", "0"], env, check=False))

        must_limit_error(run(["./scripts/lims.sh", "container", "list", "--limit", "-1"], env, check=False))
        must_limit_error(run(["./scripts/lims.sh", "sample", "list", "--limit", "-1"], env, check=False))
        must_limit_error(run(["./scripts/lims.sh", "sample", "events", sid, "--limit", "-1"], env, check=False))

        print("OK: strict --limit semantics enforced (0 => 0 rows; <0 => rc=2 error).")
        return 0

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
