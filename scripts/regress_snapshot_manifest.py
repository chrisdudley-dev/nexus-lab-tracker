#!/usr/bin/env python3
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def run(cmd, env):
    p = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        print("FAIL:", " ".join(cmd))
        print("STDOUT:\n" + p.stdout)
        print("STDERR:\n" + p.stderr)
        return 1
    return 0

def main():
    repo = Path(__file__).resolve().parents[1]
    env = os.environ.copy()

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        exports_dir = td / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)

        env["DB_PATH"] = str(td / "lims.sqlite3")

        if run([str(repo/"scripts/lims.sh"), "init"], env): return 1
        if run([str(repo/"scripts/migrate.sh"), "up"], env): return 1

        if run([str(repo/"scripts/lims.sh"), "container", "add", "--barcode", "TUBE-1", "--kind", "tube", "--location", "bench-A"], env): return 1
        if run([str(repo/"scripts/lims.sh"), "container", "add", "--barcode", "TUBE-2", "--kind", "tube", "--location", "bench-A"], env): return 1
        if run([str(repo/"scripts/lims.sh"), "sample", "add", "--external-id", "S-001", "--specimen-type", "saliva", "--container", "TUBE-1"], env): return 1
        if run([str(repo/"scripts/lims.sh"), "sample", "add", "--external-id", "S-002", "--specimen-type", "blood",  "--container", "TUBE-2"], env): return 1

        if run([str(repo/"scripts/lims.sh"), "snapshot", "export", "--exports-dir", str(exports_dir),
                "--include-sample", "S-001", "--include-sample", "S-002"], env): return 1

        snaps = sorted([d for d in exports_dir.iterdir() if d.is_dir() and d.name.startswith("snapshot-")])
        if not snaps:
            print("FAIL: no snapshot-* directory created")
            return 1
        snap = snaps[-1]

        manifest = snap / "manifest.json"
        if not manifest.exists():
            print("FAIL: manifest.json missing:", manifest)
            return 1

        doc = json.loads(manifest.read_text(encoding="utf-8"))

        # DB hash must match
        dbp = snap / "lims.sqlite3"
        want_db = sha256_file(dbp)
        got_db = doc.get("db", {}).get("sha256")
        if got_db != want_db:
            print("FAIL: manifest db sha256 mismatch")
            print("got:", got_db)
            print("want:", want_db)
            return 1

        # Included samples must match and hashes must match files
        samples = doc.get("included_exports", {}).get("samples", [])
        got_ids = sorted([x.get("external_id") for x in samples])
        if got_ids != ["S-001", "S-002"]:
            print("FAIL: manifest included sample ids mismatch")
            print("got:", got_ids)
            return 1

        for x in samples:
            fp = Path(x["path"])
            if not fp.exists():
                print("FAIL: manifest points to missing export:", fp)
                return 1
            want = sha256_file(fp)
            got = x.get("sha256")
            if got != want:
                print("FAIL: manifest export sha256 mismatch:", fp)
                print("got:", got)
                print("want:", want)
                return 1

        # Tarball (if exists) must be recorded and hash must match
        tarball = Path(str(snap) + ".tar.gz")
        if tarball.exists():
            t = doc.get("tarball")
            if not isinstance(t, dict) or not t.get("path") or not t.get("sha256"):
                print("FAIL: tarball exists but manifest.tarball is missing/invalid")
                print("tarball:", tarball)
                print("manifest.tarball:", t)
                return 1
            want = sha256_file(tarball)
            got = t.get("sha256")
            if got != want:
                print("FAIL: manifest tarball sha256 mismatch")
                print("got:", got)
                print("want:", want)
                return 1

        print("OK: snapshot manifest exists and hashes match.")
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
