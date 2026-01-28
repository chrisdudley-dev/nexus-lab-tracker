#!/usr/bin/env python3
import argparse, hashlib, json, sys
from pathlib import Path

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def fail(msg: str, code: int = 2):
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)

def main():
    ap = argparse.ArgumentParser(description="Validate snapshot manifest.json against snapshot contents.")
    ap.add_argument("--snap-dir", required=True, help="Path to snapshot directory (snapshot-*)")
    ap.add_argument("--tarball", default="", help="Optional path to tarball; if empty, checks sibling ${snap_dir}.tar.gz if present.")
    ap.add_argument("--check-included", action="store_true", help="Verify included export file hashes listed in manifest.")
    args = ap.parse_args()

    snap = Path(args.snap_dir)
    if not snap.is_dir():
        fail(f"--snap-dir is not a directory: {snap}")

    mf = snap / "manifest.json"
    if not mf.exists():
        # Not an error: manifest is optional for backwards compatibility.
        print("OK: manifest.json not present; skipping manifest validation.")
        return 0

    try:
        doc = json.loads(mf.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"manifest.json is not valid JSON: {e}")

    # DB hash
    dbp = snap / "lims.sqlite3"
    if not dbp.exists():
        fail(f"snapshot db missing: {dbp}")

    want_db = sha256_file(dbp)
    got_db = (doc.get("db") or {}).get("sha256")
    if got_db != want_db:
        fail(f"manifest db sha256 mismatch (got {got_db}, want {want_db})")

    # Tarball hash (if tar exists, require manifest entry)
    tar_path = Path(args.tarball) if args.tarball else Path(str(snap) + ".tar.gz")
    if tar_path.exists():
        t = doc.get("tarball")
        if not isinstance(t, dict) or not t.get("sha256"):
            fail(f"tarball exists but manifest.tarball missing/invalid ({tar_path})")
        want_tar = sha256_file(tar_path)
        got_tar = t.get("sha256")
        if got_tar != want_tar:
            fail(f"manifest tarball sha256 mismatch (got {got_tar}, want {want_tar})")

    # Included exports (optional strictness)
    if args.check_included:
        inc = (doc.get("included_exports") or {}).get("samples") or []
        for ent in inc:
            pth = ent.get("path")
            want = ent.get("sha256")
            if not pth:
                fail("manifest included_exports.samples entry missing path")
            fp = Path(pth)
            if not fp.exists():
                fail(f"manifest included export missing: {fp}")
            if want is None:
                fail(f"manifest included export sha256 missing: {fp}")
            got = sha256_file(fp)
            if got != want:
                fail(f"manifest included export sha256 mismatch for {fp} (got {got}, want {want})")

    print("OK: manifest.json validated (db/tarball/included exports).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
