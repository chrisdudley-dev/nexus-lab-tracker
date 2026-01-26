#!/usr/bin/env python3
import os, subprocess, tempfile, time

def run(cmd, env, check=True):
    p = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed (rc={p.returncode}): {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return p

def move_cmd(env, sample_identifier: str, container_identifier: str):
    # Determine interface by inspecting help text.
    h = run(["./scripts/lims.sh", "sample", "move", "-h"], env, check=False)
    helptext = (h.stdout or "") + "\n" + (h.stderr or "")

    # New interface: --to required
    if "--to" in helptext:
        # argparse typically allows options before/after; usage shows sample last.
        return ["./scripts/lims.sh", "sample", "move", "--to", container_identifier, sample_identifier]

    # Older interface: --container
    if "--container" in helptext:
        return ["./scripts/lims.sh", "sample", "move", sample_identifier, "--container", container_identifier]

    # Fallback: positional container
    return ["./scripts/lims.sh", "sample", "move", sample_identifier, container_identifier]

def main() -> int:
    fd, db_path = tempfile.mkstemp(prefix="nexus-lims-sample-move-precheck.", suffix=".sqlite")
    os.close(fd)
    env = os.environ.copy()
    env["DB_PATH"] = db_path

    try:
        run(["./scripts/lims.sh", "init"], env)
        run(["./scripts/migrate.sh", "up"], env)

        sfx = str(int(time.time() * 1000))
        t1 = f"TUBE-A-{sfx}"
        t2 = f"TUBE-B-{sfx}"
        t3 = f"TUBE-C-{sfx}"
        s1 = f"S-1-{sfx}"
        s2 = f"S-2-{sfx}"

        # tube defaults exclusive via kind defaults
        run(["./scripts/lims.sh", "container", "add", "--barcode", t1, "--kind", "tube", "--location", "bench"], env)
        run(["./scripts/lims.sh", "container", "add", "--barcode", t2, "--kind", "tube", "--location", "bench"], env)
        run(["./scripts/lims.sh", "container", "add", "--barcode", t3, "--kind", "tube", "--location", "bench"], env)

        run(["./scripts/lims.sh", "sample", "add", "--external-id", s1, "--specimen-type", "blood", "--container", t1], env)
        run(["./scripts/lims.sh", "sample", "add", "--external-id", s2, "--specimen-type", "blood", "--container", t2], env)

        # Attempt illegal move: move s2 into t1 (occupied exclusive)
        p_bad = run(move_cmd(env, s2, t1), env, check=False)
        if p_bad.returncode != 2:
            print("FAIL: expected rc=2 when moving into occupied exclusive container")
            print("CMD:", " ".join(move_cmd(env, s2, t1)))
            print("STDOUT:\n" + p_bad.stdout)
            print("STDERR:\n" + p_bad.stderr)
            return 1

        must = [
            "ERROR: target container is exclusive and already occupied",
            f"Container: {t1}",
            "Occupied by:",
            s1,
        ]
        for token in must:
            if token not in (p_bad.stdout or ""):
                print(f"FAIL: expected stdout to contain: {token}")
                print("CMD:", " ".join(move_cmd(env, s2, t1)))
                print("STDOUT:\n" + p_bad.stdout)
                print("STDERR:\n" + p_bad.stderr)
                return 1

        # Legal move: move s2 into empty t3
        p_ok = run(move_cmd(env, s2, t3), env, check=False)
        if p_ok.returncode != 0:
            print("FAIL: expected rc=0 moving into empty exclusive container")
            print("CMD:", " ".join(move_cmd(env, s2, t3)))
            print("STDOUT:\n" + p_ok.stdout)
            print("STDERR:\n" + p_ok.stderr)
            return 1

        print("OK: sample move precheck blocks occupied exclusive containers with contextual error; allows legal moves.")
        return 0

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
