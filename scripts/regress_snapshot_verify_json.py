#!/usr/bin/env python3
import json, os, subprocess, tempfile
from pathlib import Path

def run(cmd, env, cwd):
    return subprocess.run(cmd, env=env, cwd=cwd, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def main():
    repo = Path(__file__).resolve().parents[1]
    env = os.environ.copy()

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        exports = td / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        env["DB_PATH"] = str(td / "lims.sqlite3")

        setup = [
            [str(repo/"scripts/lims.sh"), "init"],
            [str(repo/"scripts/migrate.sh"), "up"],
            [str(repo/"scripts/lims.sh"), "container", "add", "--barcode", "TUBE-1", "--kind", "tube", "--location", "bench-A"],
            [str(repo/"scripts/lims.sh"), "sample", "add", "--external-id", "S-001", "--specimen-type", "saliva", "--container", "TUBE-1"],
            [str(repo/"scripts/lims.sh"), "snapshot", "export", "--exports-dir", str(exports), "--include-sample", "S-001"],
        ]
        for cmd in setup:
            p = run(cmd, env, repo)
            if p.returncode != 0:
                print("FAIL:", " ".join(cmd))
                print("STDOUT:\n"+p.stdout)
                print("STDERR:\n"+p.stderr)
                return 1

        tarballs = sorted(exports.glob("snapshot-*.tar.gz"))
        if not tarballs:
            print("FAIL: expected snapshot-*.tar.gz")
            return 1
        tarball = tarballs[-1]

        env2 = env.copy()
        env2["SNAPSHOT_ARTIFACT"] = str(tarball)

        p = run([str(repo/"scripts/snapshot_verify.sh"), "--json"], env2, repo)
        if p.returncode != 0:
            print("FAIL: snapshot_verify --json rc=", p.returncode)
            print("STDOUT:\n"+p.stdout)
            print("STDERR:\n"+p.stderr)
            return 1

        doc = json.loads(p.stdout.strip())
        if doc.get("schema") != "nexus_snapshot_verify_result" or doc.get("ok") is not True or doc.get("rc") != 0:
            print("FAIL: unexpected JSON contract:", doc)
            return 1

        print("OK: snapshot verify --json emits valid JSON contract.")
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
