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
    fd, db_path = tempfile.mkstemp(prefix="nexus-lims-status.", suffix=".sqlite")
    os.close(fd)
    env = os.environ.copy()
    env["DB_PATH"] = db_path

    try:
        run(["./scripts/lims.sh", "init"], env)

        sfx = str(int(time.time() * 1000))
        c1 = f"TPT-C1-{sfx}"
        sid = f"TPT-S-{sfx}"

        run(["./scripts/lims.sh", "container", "add", "--barcode", c1, "--kind", "tube", "--location", "bench"], env)
        run(["./scripts/lims.sh", "sample", "add", "--external-id", sid, "--specimen-type", "blood", "--container", c1], env)

        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        row = cur.execute("SELECT id FROM samples WHERE external_id = ?", (sid,)).fetchone()
        if not row:
            print("ERROR: sample not found after creation")
            return 1
        sample_id = int(row["id"])

        def count_events() -> int:
            return int(cur.execute(
                "SELECT COUNT(*) AS n FROM sample_events WHERE sample_id = ?",
                (sample_id,),
            ).fetchone()["n"])

        before = count_events()

        # Allowed: received -> processing (should add exactly one event)
        run(["./scripts/lims.sh", "sample", "status", sid, "--to", "processing", "--note", "regress allowed"], env)
        after_allowed = count_events()
        if after_allowed != before + 1:
            print(f"ERROR: expected +1 event after allowed transition; before={before} after={after_allowed}")
            return 1

        # Alias: "testing" should map to "processing" (no-op now, should NOT add an event)
        run(["./scripts/lims.sh", "sample", "status", sid, "--to", "testing", "--note", "regress alias"], env)
        after_alias = count_events()
        if after_alias != after_allowed:
            print(f"ERROR: expected no new event on alias no-op; after_allowed={after_allowed} after_alias={after_alias}")
            return 1

        # No-op: processing -> processing (should add zero events)
        run(["./scripts/lims.sh", "sample", "status", sid, "--to", "processing", "--note", "regress noop"], env)
        after_noop = count_events()
        if after_noop != after_allowed:
            print(f"ERROR: expected no new event on no-op; after_allowed={after_allowed} after_noop={after_noop}")
            return 1

        # Disallowed: processing -> received (must fail, must not add events)
        p = run(["./scripts/lims.sh", "sample", "status", sid, "--to", "received", "--note", "regress disallowed"], env, check=False)
        if p.returncode == 0:
            print("ERROR: expected disallowed transition to fail but it succeeded")
            print(p.stdout)
            return 1

        after_disallowed = count_events()
        if after_disallowed != after_allowed:
            print(f"ERROR: expected no new event after disallowed transition; after_allowed={after_allowed} after_disallowed={after_disallowed}")
            print("STDOUT:\n" + p.stdout)
            print("STDERR:\n" + p.stderr)
            return 1

        # Invalid status value (must fail, must not add events)
        p2 = run(["./scripts/lims.sh", "sample", "status", sid, "--to", "not-a-status"], env, check=False)
        if p2.returncode == 0:
            print("ERROR: expected invalid status to fail but it succeeded")
            print(p2.stdout)
            return 1

        after_invalid = count_events()
        if after_invalid != after_allowed:
            print(f"ERROR: expected no new event after invalid status; after_allowed={after_allowed} after_invalid={after_invalid}")
            print("STDOUT:\n" + p2.stdout)
            print("STDERR:\n" + p2.stderr)
            return 1

        print("OK: status transition enforcement (allowed/no-op/disallowed/invalid/alias) behaves as expected.")
        return 0

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
