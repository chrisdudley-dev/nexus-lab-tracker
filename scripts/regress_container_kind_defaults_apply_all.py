#!/usr/bin/env python3
import os, subprocess, tempfile, sqlite3, time, re

def run(cmd, env, check=True):
    p = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed (rc={p.returncode}): {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return p

def parse_applied_count(stdout: str) -> int:
    # Accept: "OK: applied kind default to N container(s)" OR "defaults"
    m = re.search(r"applied kind default[s]?\s+to\s+(\d+)\s+container", stdout or "", re.I)
    if not m:
        raise RuntimeError(f"Could not parse applied count from stdout:\n{stdout}")
    return int(m.group(1))

def main() -> int:
    fd, db_path = tempfile.mkstemp(prefix="nexus-lims-kind-defaults-apply-all.", suffix=".sqlite")
    os.close(fd)
    env = os.environ.copy()
    env["DB_PATH"] = db_path

    try:
        run(["./scripts/lims.sh", "init"], env)
        run(["./scripts/migrate.sh", "up"], env)

        sfx = str(int(time.time() * 1000))
        bag   = f"BAG-{sfx}"
        tube  = f"TUBE-{sfx}"
        plate = f"PLATE-{sfx}"

        # Ensure a non-seeded kind exists in defaults so apply-all has something beyond tube/vial.
        run(["./scripts/lims.sh", "container", "kind-defaults", "set", "bag", "on"], env)

        # Create three containers: bag (has default), tube (seed default), plate (no default).
        run(["./scripts/lims.sh", "container", "add", "--barcode", bag,   "--kind", "bag",   "--location", "bench"], env)
        run(["./scripts/lims.sh", "container", "add", "--barcode", tube,  "--kind", "tube",  "--location", "bench"], env)
        run(["./scripts/lims.sh", "container", "add", "--barcode", plate, "--kind", "plate", "--location", "bench"], env)

        # Drift: flip bag + tube away from their defaults; flip plate too (but plate has NO default).
        run(["./scripts/lims.sh", "container", "set-exclusive", bag,   "off"], env)
        run(["./scripts/lims.sh", "container", "set-exclusive", tube,  "off"], env)
        run(["./scripts/lims.sh", "container", "set-exclusive", plate, "on"],  env)

        # Apply all defaults. Should correct bag + tube only => 2 updates.
        p_all = run(["./scripts/lims.sh", "container", "kind-defaults", "apply", "--all"], env, check=False)
        if p_all.returncode != 0:
            print("FAIL: expected apply --all rc=0")
            print("STDOUT:\n" + (p_all.stdout or ""))
            print("STDERR:\n" + (p_all.stderr or ""))
            return 1

        n = parse_applied_count(p_all.stdout or "")
        if n != 2:
            print("FAIL: expected apply --all to update exactly 2 containers (bag + tube).")
            print("STDOUT:\n" + (p_all.stdout or ""))
            print("STDERR:\n" + (p_all.stderr or ""))
            return 1

        # Validate final values directly in SQLite.
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT barcode, kind, is_exclusive FROM containers ORDER BY barcode").fetchall()
        m = {r["barcode"]: (r["kind"], int(r["is_exclusive"])) for r in rows}

        # bag default is 1; tube default is 1; plate has no default so should remain unchanged (still 1).
        if m[bag][1] != 1:
            print("FAIL: bag should be exclusive after apply --all")
            print(m)
            return 1
        if m[tube][1] != 1:
            print("FAIL: tube should be exclusive after apply --all")
            print(m)
            return 1
        if m[plate][1] != 1:
            print("FAIL: plate should remain unchanged (no default) and stay exclusive=1")
            print(m)
            return 1

        # Guardrails:
        p_bad1 = run(["./scripts/lims.sh", "container", "kind-defaults", "apply", "--all", "bag"], env, check=False)
        if p_bad1.returncode != 2 or "ERROR:" not in (p_bad1.stdout or ""):
            print("FAIL: expected rc=2 ERROR when providing both --all and kind")
            print("STDOUT:\n" + (p_bad1.stdout or ""))
            print("STDERR:\n" + (p_bad1.stderr or ""))
            return 1

        p_bad2 = run(["./scripts/lims.sh", "container", "kind-defaults", "apply"], env, check=False)
        if p_bad2.returncode != 2 or "ERROR:" not in (p_bad2.stdout or ""):
            print("FAIL: expected rc=2 ERROR when providing neither kind nor --all")
            print("STDOUT:\n" + (p_bad2.stdout or ""))
            print("STDERR:\n" + (p_bad2.stderr or ""))
            return 1

        print("OK: kind-defaults apply --all updates drifted rows for defaulted kinds only; guardrails enforced.")
        return 0
    finally:
        try:
            os.remove(db_path)
        except FileNotFoundError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
