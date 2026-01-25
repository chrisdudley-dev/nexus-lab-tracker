#!/usr/bin/env python3
import json, os, subprocess, tempfile, time

def run(cmd, env, check=True):
    p = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed (rc={p.returncode}): {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return p

def json_rows(stdout: str):
    rows = []
    for ln in stdout.splitlines():
        ln = ln.strip()
        if ln.startswith("{"):
            rows.append(json.loads(ln))
    return rows

def main() -> int:
    fd, db_path = tempfile.mkstemp(prefix="nexus-lims-list.", suffix=".sqlite")
    os.close(fd)
    env = os.environ.copy()
    env["DB_PATH"] = db_path

    try:
        run(["./scripts/lims.sh", "init"], env)

        sfx = str(int(time.time() * 1000))
        c1 = f"LIST-C-{sfx}"
        s_proc = f"LIST-P-{sfx}"
        s_recv = f"LIST-R-{sfx}"

        run(["./scripts/lims.sh", "container", "add", "--barcode", c1, "--kind", "tube", "--location", "bench"], env)

        run(["./scripts/lims.sh", "sample", "add", "--external-id", s_recv, "--specimen-type", "blood", "--status", "received", "--container", c1], env)
        run(["./scripts/lims.sh", "sample", "add", "--external-id", s_proc, "--specimen-type", "blood", "--status", "processing", "--container", c1], env)

        # Alias filter: "testing" -> "processing" (also with whitespace/case)
        p = run(["./scripts/lims.sh", "sample", "list", "--status", "  TeStInG  ", "--limit", "50"], env, check=True)
        rows = json_rows(p.stdout)
        if not rows:
            print("ERROR: expected at least 1 row for alias status filter 'testing'")
            print(p.stdout)
            return 1
        if any(r.get("status") != "processing" for r in rows):
            print("ERROR: alias filter returned non-processing rows")
            print(p.stdout)
            return 1
        if not any(r.get("external_id") == s_proc for r in rows):
            print("ERROR: alias filter did not include expected processing sample")
            print(p.stdout)
            return 1

        # Invalid status should fail rc=2
        p2 = run(["./scripts/lims.sh", "sample", "list", "--status", "nonsense"], env, check=False)
        if p2.returncode == 0:
            print("ERROR: expected non-zero rc for invalid status filter")
            print(p2.stdout)
            return 1
        if "ERROR: invalid status" not in (p2.stdout + p2.stderr):
            print("ERROR: expected invalid status error message")
            print("STDOUT:\n" + p2.stdout)
            print("STDERR:\n" + p2.stderr)
            return 1

        print("OK: sample list --status normalization (alias/whitespace) and invalid rejection behave as expected.")
        return 0

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
