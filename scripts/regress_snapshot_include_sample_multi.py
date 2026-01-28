#!/usr/bin/env python3
import os, json, subprocess, tempfile
from pathlib import Path

def run(cmd, env, check=True):
    p = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed (rc={p.returncode}): {' '.join(cmd)}\n"
            f"STDOUT:\n{p.stdout}\n"
            f"STDERR:\n{p.stderr}"
        )
    return p

def snapshot_dirs(exports_dir: Path):
    return {d.name for d in exports_dir.iterdir() if d.is_dir() and d.name.startswith("snapshot-")}

def run_export(exports_dir: Path, env, include_list):
    before = snapshot_dirs(exports_dir)
    cmd = ["./scripts/lims.sh", "snapshot", "export", "--exports-dir", str(exports_dir)]
    for ident in include_list:
        cmd += ["--include-sample", ident]
    p = run(cmd, env, check=False)
    if p.returncode != 0:
        raise RuntimeError(f"snapshot export failed rc={p.returncode}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")

    after = snapshot_dirs(exports_dir)
    created = sorted(after - before)
    if len(created) != 1:
        raise RuntimeError(f"expected exactly 1 new snapshot dir, got {created}")
    return exports_dir / created[0]

def assert_sample_json(snap: Path, ident: str, should_exist: bool):
    f = snap / "exports" / "samples" / f"sample-{ident}.json"
    alt = snap / "exports" / "samples" / f"sample-{ident}_.json"
    if should_exist:
        if not f.exists():
            raise RuntimeError(f"missing expected export: {f}")
        if alt.exists():
            raise RuntimeError(f"legacy underscore filename produced: {alt}")
        obj = json.loads(f.read_text(encoding="utf-8"))
        if obj.get("sample", {}).get("external_id") != ident:
            raise RuntimeError(f"external_id mismatch in {f}: {obj.get('sample')}")
    else:
        if f.exists() or alt.exists():
            raise RuntimeError(f"unexpected export present for {ident}: {f} or {alt}")

def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="nexus-lims-snap-inc-multi."))
    db_path = tmp / "lims.sqlite3"
    exports_dir = tmp / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["DB_PATH"] = str(db_path)

    run(["./scripts/lims.sh", "init"], env)
    run(["./scripts/migrate.sh", "up"], env)

    # Two containers: exclusivity enforced
    run(["./scripts/lims.sh", "container", "add", "--barcode", "TUBE-1", "--kind", "tube", "--location", "bench-A"], env)
    run(["./scripts/lims.sh", "container", "add", "--barcode", "TUBE-2", "--kind", "tube", "--location", "bench-A"], env)

    run(["./scripts/lims.sh", "sample", "add", "--external-id", "S-001", "--specimen-type", "saliva", "--container", "TUBE-1"], env)
    run(["./scripts/lims.sh", "sample", "add", "--external-id", "S-002", "--specimen-type", "blood",  "--container", "TUBE-2"], env)

    # 1) Multi include must export both
    snap1 = run_export(exports_dir, env, ["S-001", "S-002"])
    assert_sample_json(snap1, "S-001", True)
    assert_sample_json(snap1, "S-002", True)

    # 2) Stale env must NOT leak in (lims.sh unsets it before parsing)
    env2 = env.copy()
    env2["SNAPSHOT_INCLUDE_SAMPLES"] = "S-001"
    snap2 = run_export(exports_dir, env2, ["S-002"])
    assert_sample_json(snap2, "S-002", True)
    assert_sample_json(snap2, "S-001", False)

    print("OK: multi-include accumulates; stale env does not leak; snapshot dirs are unique.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
