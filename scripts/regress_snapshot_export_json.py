#!/usr/bin/env python3
import json, os, subprocess, tempfile
from pathlib import Path

def run(cmd, env):
    return subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="nexus-lims-snap-json."))
    db_path = tmp / "lims.sqlite3"
    exports_dir = tmp / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["DB_PATH"] = str(db_path)

    # Setup data (two containers: exclusivity enforced)
    for cmd in [
        ["./scripts/lims.sh","init"],
        ["./scripts/migrate.sh","up"],
        ["./scripts/lims.sh","container","add","--barcode","TUBE-1","--kind","tube","--location","bench-A"],
        ["./scripts/lims.sh","container","add","--barcode","TUBE-2","--kind","tube","--location","bench-A"],
        ["./scripts/lims.sh","sample","add","--external-id","S-001","--specimen-type","saliva","--container","TUBE-1"],
        ["./scripts/lims.sh","sample","add","--external-id","S-002","--specimen-type","blood","--container","TUBE-2"],
    ]:
        p = run(cmd, env)
        if p.returncode != 0:
            print("FAIL setup:", " ".join(cmd))
            print("STDOUT:\n", p.stdout)
            print("STDERR:\n", p.stderr)
            return 1

    # JSON export
    p = run([
        "./scripts/lims.sh","snapshot","export",
        "--exports-dir", str(exports_dir),
        "--include-sample","S-001",
        "--include-sample","S-002",
        "--json",
    ], env)

    if p.returncode != 0:
        print("FAIL: snapshot export --json rc!=0")
        print("STDOUT:\n", p.stdout)
        print("STDERR:\n", p.stderr)
        return 1

    # stdout must be JSON (single object)
    try:
        doc = json.loads(p.stdout.strip())
    except Exception as e:
        print("FAIL: stdout is not valid JSON:", e)
        print("STDOUT:\n", p.stdout)
        print("STDERR:\n", p.stderr)
        return 1

    # minimal contract
    if doc.get("schema") != "nexus_snapshot_export_result" or doc.get("schema_version") != 1 or doc.get("ok") is not True:
        print("FAIL: JSON schema/fields unexpected:", doc)
        return 1

    snap_dir = Path(doc.get("snapshot_dir",""))
    tarball = Path(doc.get("tarball",""))

    if not snap_dir.is_dir():
        print("FAIL: snapshot_dir missing:", snap_dir)
        return 1
    if not (snap_dir / "manifest.json").exists():
        print("FAIL: manifest.json missing")
        return 1
    if not tarball.is_file():
        print("FAIL: tarball missing:", tarball)
        return 1

    inc = set(doc.get("included_samples", []))
    if inc != {"S-001","S-002"}:
        print("FAIL: included_samples mismatch:", doc.get("included_samples"))
        return 1

    print("OK: snapshot export --json emits valid contract and artifacts exist.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
