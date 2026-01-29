# Nexus Lab Tracker

- Sample event timestamps now include fractional seconds (UTC) for improved chronological clarity; event listings remain deterministically ordered by (occurred_at, id).

## Snapshot Operations

This project supports reproducible database snapshots (for backups, audits, and diffing changes) via:

- ./scripts/lims.sh snapshot export
- ./scripts/lims.sh snapshot verify <artifact>
- ./scripts/lims.sh snapshot doctor <artifact>
- ./scripts/lims.sh snapshot diff <A> <B>
- ./scripts/lims.sh snapshot latest
- ./scripts/lims.sh snapshot diff-latest
- ./scripts/lims.sh snapshot pin / unpin / pins
- ./scripts/lims.sh snapshot prune
- ./scripts/lims.sh snapshot gc

### Concepts

- Snapshot tarball: snapshot-YYYYMMDD-HHMMSSZ.tar.gz in EXPORTS_DIR (or ./exports).
- Snapshot dir: matching directory name (same basename as tarball) containing exported artifacts.
- Verification tools operate on temporary copies and do not mutate the live DB.

### Golden workflows

1) Create a snapshot
   ./scripts/lims.sh snapshot export

2) Compare newest vs previous snapshot
   ./scripts/lims.sh snapshot diff-latest
   ./scripts/lims.sh snapshot diff-latest --json-only

3) Deep verification (integrity + FK + migrations + invariants)
   ./scripts/lims.sh snapshot verify "$(./scripts/lims.sh snapshot latest)"
   ./scripts/lims.sh snapshot doctor "$(./scripts/lims.sh snapshot latest)" --json-only

4) Pin a known-good baseline (never deleted by prune/gc)
   ./scripts/lims.sh snapshot pin --n 1
   ./scripts/lims.sh snapshot pins

5) Retention (dry-run by default)
   ./scripts/lims.sh snapshot prune --keep 10
   ./scripts/lims.sh snapshot prune --keep 10 --apply

6) Consistency cleanup (dry-run by default)
   ./scripts/lims.sh snapshot gc
   ./scripts/lims.sh snapshot gc --apply

### Notes

- Tube/vial containers are exclusive by default; regressions use separate containers when creating multiple samples.
- For CI confidence: run `./scripts/regress_core.sh` before pushing.




## License
This project is licensed under the GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later). See `LICENSE`.

### Licensing intent
Nexus Lab Tracker is AGPL-3.0-or-later to keep the core implementation open, including when deployed as a network service.
Clients and integrations are intended to interact via the CLI and/or HTTP API boundary.
