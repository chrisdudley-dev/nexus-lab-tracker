#!/usr/bin/env python3
import json, os, sqlite3, subprocess, tempfile, time

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
    fd, db_path = tempfile.mkstemp(prefix="nexus-lims-order.", suffix=".sqlite")
    os.close(fd)
    env = os.environ.copy()
    env["DB_PATH"] = db_path

    try:
        run(["./scripts/lims.sh", "init"], env)

        sfx = str(int(time.time() * 1000))
        bc1 = f"TIE-C1-{sfx}"
        bc2 = f"TIE-C2-{sfx}"
        s1  = f"TIE-S1-{sfx}"
        s2  = f"TIE-S2-{sfx}"

        # Create two containers
        run(["./scripts/lims.sh", "container", "add", "--barcode", bc1, "--kind", "tube"], env)
        run(["./scripts/lims.sh", "container", "add", "--barcode", bc2, "--kind", "tube"], env)

        # Create two samples
        run(["./scripts/lims.sh", "sample", "add", "--external-id", s1, "--specimen-type", "blood"], env)
        run(["./scripts/lims.sh", "sample", "add", "--external-id", s2, "--specimen-type", "blood"], env)

        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        c1 = cur.execute("SELECT id FROM containers WHERE barcode = ?", (bc1,)).fetchone()
        c2 = cur.execute("SELECT id FROM containers WHERE barcode = ?", (bc2,)).fetchone()
        if not c1 or not c2:
            print("ERROR: failed to resolve container ids")
            return 1
        id1, id2 = int(c1["id"]), int(c2["id"])

        sm1 = cur.execute("SELECT id FROM samples WHERE external_id = ?", (s1,)).fetchone()
        sm2 = cur.execute("SELECT id FROM samples WHERE external_id = ?", (s2,)).fetchone()
        if not sm1 or not sm2:
            print("ERROR: failed to resolve sample ids")
            return 1
        sid1, sid2 = int(sm1["id"]), int(sm2["id"])

        # Force timestamp ties
        tie_ts = "2026-01-01T00:00:00.000000+00:00"
        cur.execute(
            "UPDATE containers SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
            (tie_ts, tie_ts, id1, id2),
        )
        cur.execute(
            "UPDATE samples SET received_at = ? WHERE id IN (?, ?)",
            (tie_ts, sid1, sid2),
        )
        con.commit()

        # Verify container list tie-break: created_at DESC, id DESC
        p = run(["./scripts/lims.sh", "container", "list", "--limit", "50"], env)
        rows = [r for r in json_rows(p.stdout) if r.get("barcode") in (bc1, bc2)]
        if len(rows) != 2:
            print("ERROR: expected exactly 2 matching containers in list output")
            print(p.stdout)
            return 1

        expected_first = max(id1, id2)
        if int(rows[0].get("id")) != expected_first:
            print("ERROR: container list tie-break order incorrect")
            print("expected first id:", expected_first)
            print("got ids:", [x.get("id") for x in rows])
            return 1

        # Verify sample list tie-break: received_at DESC, id DESC
        p2 = run(["./scripts/lims.sh", "sample", "list", "--limit", "50"], env)
        rows2 = [r for r in json_rows(p2.stdout) if r.get("external_id") in (s1, s2)]
        if len(rows2) != 2:
            print("ERROR: expected exactly 2 matching samples in list output")
            print(p2.stdout)
            return 1

        expected_first_s = max(sid1, sid2)
        if int(rows2[0].get("id")) != expected_first_s:
            print("ERROR: sample list tie-break order incorrect")
            print("expected first id:", expected_first_s)
            print("got ids:", [y.get("id") for y in rows2])
            return 1

        print("OK: deterministic ordering under timestamp ties for container list and sample list (ORDER BY ... DESC, id DESC).")
        return 0

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
