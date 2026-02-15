# Nexus Lab Tracker

LIMS for tracking containers, samples, and events with a deterministic CLI and reproducible SQLite snapshot workflows.

- Sample event timestamps include fractional seconds (UTC) for improved chronological clarity; event listings remain deterministically ordered by `(occurred_at, id)`.

## 60-second demo

**Prereqs**
- Python 3 (recommended: 3.10+)
- Bash (Linux/macOS; on Windows use WSL2)

```bash
# Initialize a local SQLite DB and run migrations
./scripts/lims.sh init
./scripts/migrate.sh up

# Create a container and add a sample (use your own IDs)
./scripts/lims.sh container add --barcode TUBE-1 --kind tube --location bench-A
./scripts/lims.sh sample add --external-id S-001 --specimen-type saliva --container TUBE-1

# Sanity: run the core regression gate
./scripts/regress_core.sh
```

For more, see `docs/quickstart.md`.

## Snapshot operations

This project supports reproducible database snapshots (for backups, audits, and diffing changes) via:

- `./scripts/lims.sh snapshot export`
- `./scripts/lims.sh snapshot verify <artifact>`
- `./scripts/lims.sh snapshot doctor <artifact>`
- `./scripts/lims.sh snapshot diff <A> <B>`
- `./scripts/lims.sh snapshot latest`
- `./scripts/lims.sh snapshot diff-latest`
- `./scripts/lims.sh snapshot pin / unpin / pins`
- `./scripts/lims.sh snapshot prune`
- `./scripts/lims.sh snapshot gc`

### Concepts

- Snapshot tarball: `snapshot-YYYYMMDD-HHMMSSZ.tar.gz` in `EXPORTS_DIR` (or `./exports`).
- Snapshot dir: matching directory name (same basename as tarball) containing exported artifacts.
- Verification tools operate on temporary copies and do not mutate the live DB.

### Golden workflows

1) Create a snapshot  
   `./scripts/lims.sh snapshot export`

2) Compare newest vs previous snapshot  
   `./scripts/lims.sh snapshot diff-latest`  
   `./scripts/lims.sh snapshot diff-latest --json-only`

3) Deep verification (integrity + FK + migrations + invariants)  
   `./scripts/lims.sh snapshot verify "$(./scripts/lims.sh snapshot latest)"`  
   `./scripts/lims.sh snapshot doctor "$(./scripts/lims.sh snapshot latest)" --json-only`

4) Pin a known-good baseline (never deleted by prune/gc)  
   `./scripts/lims.sh snapshot pin --n 1`  
   `./scripts/lims.sh snapshot pins`

5) Retention (dry-run by default)  
   `./scripts/lims.sh snapshot prune --keep 10`  
   `./scripts/lims.sh snapshot prune --keep 10 --apply`

6) Consistency cleanup (dry-run by default)  
   `./scripts/lims.sh snapshot gc`  
   `./scripts/lims.sh snapshot gc --apply`

### Notes

- Tube/vial containers are exclusive by default; regressions use separate containers when creating multiple samples.
- For CI confidence: run `./scripts/regress_core.sh` before pushing changes.

## License

This project is licensed under the GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later). See `LICENSE`.

### Licensing intent

Nexus Lab Tracker is AGPL-3.0-or-later to keep the core implementation open, including when deployed as a network service. Clients and integrations are intended to interact via the CLI and/or HTTP API boundary.

## Contributing

Contributions are welcome. Please read `CONTRIBUTING.md` for expectations and run `./scripts/regress_core.sh` before pushing changes. If you are new to the project, check issues labeled “good first issue.”

## Stability and versioning

This project prioritizes deterministic behavior and operator safety. The CLI and local HTTP API are treated as contracts.

Stability expectations:
- Human-facing output may evolve, but safety semantics and exit codes should remain stable.
- JSON outputs are intended for automation; changes that break JSON parsing or schema fields require a clear justification and updated regressions.

Versioning approach:
- The API error envelope and machine-readable outputs use explicit schema identifiers (for example, `schema` and `schema_version`) to enable backwards-compatible evolution.
- Behavioral changes are considered “breaking” if they alter safety semantics, determinism guarantees, exit codes, or documented JSON contracts.

## Docs

- Quickstart: `docs/quickstart.md`
- Index: `docs/README.md`


## Download latest snapshot (Web UI)

After running the snapshot export from the web UI, a **Download latest snapshot** link appears.
It downloads from:

- `GET /exports/latest` (streams `snapshot.tar.gz`)
- `HEAD /exports/latest` (headers only)

The server selects the most recent `*.tar.gz` under `exports/api` (server-controlled; `Cache-Control: no-store`).

Local run:
- `./scripts/lims_api.sh --port 8087`

## Demo

- Demo guide: `docs/DEMO.md`
- API route map + curl templates: `docs/DEMO_API_CURL.md`
- Proof runner (writes proof log under `report/`): `./scripts/demo_smoke.sh`


## Canonical repo layout (M1)
- Frontend: `frontend/`
- API: `uvicorn api.main:app`
- Repo layout notes: `docs/repo-layout.md`

### Run (dev)

API:
```bash
uvicorn api.main:app --host 127.0.0.1 --port 8789 --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```
