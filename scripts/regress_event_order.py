#!/usr/bin/env python3
import json, os, re, sqlite3, subprocess, tempfile, time

MS = re.compile(r"\.\d{3,6}\+00:00$")

def run(args, env, quiet=True):
    return subprocess.run(
        args,
        env=env,
        check=True,
        text=True,
        stdout=(subprocess.DEVNULL if quiet else subprocess.PIPE),
        stderr=subprocess.PIPE,
    )

def try_cmd(cmds, env):
    last = None
    for c in cmds:
        try:
            run(c, env, quiet=True)
            return
        except subprocess.CalledProcessError as e:
            last = e
    raise last

def main():
    fd, db_path = tempfile.mkstemp(prefix="nexus-lims-order.", suffix=".sqlite")
    os.close(fd)
    env = os.environ.copy()
    env["DB_PATH"] = db_path

    try:
        run(["./scripts/lims.sh", "init"], env, quiet=True)

        sfx = str(int(time.time() * 1000))
        c1, c2, sid = f"TST-C1-{sfx}", f"TST2CL-{sfx}", f"TPT-S-{sfx}"

        run(["./scripts/lims.sh", "container", "add", "--barcode", c1, "--kind", "tube", "--location", "bench"], env)
        run(["./scripts/lims.sh", "container", "add", "--barcode", c2, "--kind", "tube", "--location", "bench"], env)
        run(["./scripts/lims.sh", "sample", "add", "--external-id", sid, "--specimen-type", "blood", "--status", "received", "--container", c1], env)

        try_cmd([
            ["./scripts/lims.sh", "sample", "status", sid, "--to", "processing", "--note", "regress status"],
            ["./scripts/lims.sh", "sample", "status", sid, "--status", "processing", "--note", "regress status"],
        ], env)

        try_cmd([
            ["./scripts/lims.sh", "sample", "move", sid, "--to", c2, "--note", "regress move"],
            ["./scripts/lims.sh", "sample", "move", sid, "--container", c2, "--note", "regress move"],
        ], env)

        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        row = cur.execute("SELECT id FROM samples WHERE external_id = ?", (sid,)).fetchone()
        if not row:
            print("ERROR: Sample not found after creation.")
            return 1
        sample_id = row["id"]

        last2 = cur.execute(
            "SELECT id, occurred_at FROM sample_events WHERE sample_id = ? ORDER BY id DESC LIMIT 2",
            (sample_id,),
        ).fetchall()
        if len(last2) != 2:
            print(f"ERROR: Expected 2 events, got {len(last2)}.")
            return 1

        ts = last2[0]["occurred_at"]
        cur.execute("UPDATE sample_events SET occurred_at = ? WHERE id IN (?, ?)", (ts, last2[0]["id"], last2[1]["id"]))
        con.commit()
        con.close()

        out = subprocess.check_output(["./scripts/lims.sh", "sample", "events", sid, "--limit", "5"], env=env, text=True)
        lines = [ln for ln in out.splitlines() if ln.strip().startswith("{")]
        if len(lines) < 2:
            print("ERROR: Expected JSON lines from CLI; got:\n" + out)
            return 1

        e1, e2 = json.loads(lines[0]), json.loads(lines[1])

        if (e1.get("event_type"), e2.get("event_type")) != ("container_moved", "status_changed"):
            print("ERROR: Unexpected ordering (expected container_moved then status_changed). Output:\n" + out)
            return 1

        oc1 = e1.get("occurred_at", "")
        if not MS.search(oc1):
            print(f"ERROR: occurred_at not millisecond format (.mmm+00:00): {oc1}\nOutput:\n{out}")
            return 1

        print("OK: deterministic ordering under timestamp ties (ORDER BY occurred_at DESC, id DESC).")
        return 0

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
