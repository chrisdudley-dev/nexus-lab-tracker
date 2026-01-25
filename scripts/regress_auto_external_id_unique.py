#!/usr/bin/env python3
import json, os, subprocess, tempfile

def run(cmd, env, check=True):
    p = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed (rc={p.returncode}): {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return p

def first_json(stdout: str):
    for ln in stdout.splitlines():
        ln = ln.strip()
        if ln.startswith("{"):
            return json.loads(ln)
    return None

def main() -> int:
    fd, db_path = tempfile.mkstemp(prefix="nexus-lims-extid.", suffix=".sqlite")
    os.close(fd)
    env = os.environ.copy()
    env["DB_PATH"] = db_path

    try:
        run(["./scripts/lims.sh", "init"], env)

        p1 = run(["./scripts/lims.sh", "sample", "add", "--specimen-type", "blood"], env)
        p2 = run(["./scripts/lims.sh", "sample", "add", "--specimen-type", "blood"], env)

        r1 = first_json(p1.stdout)
        r2 = first_json(p2.stdout)
        if not r1 or not r2:
            print("ERROR: expected JSON rows from sample add")
            print("STDOUT1:\n" + p1.stdout)
            print("STDOUT2:\n" + p2.stdout)
            return 1

        e1 = (r1.get("external_id") or "").strip()
        e2 = (r2.get("external_id") or "").strip()
        if not e1 or not e2:
            print("ERROR: external_id missing")
            print(p1.stdout)
            print(p2.stdout)
            return 1
        if e1 == e2:
            print("ERROR: auto-generated external_id collision")
            print("e1=", e1)
            print("e2=", e2)
            return 1

        print("OK: auto-generated external_id is unique across rapid consecutive creates.")
        return 0

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
