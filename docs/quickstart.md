## Quickstart (60 seconds)
This is a minimal end-to-end run that proves the CLI and snapshot tooling work.

Copy and paste:
```bash
set -euo pipefail
cd ~/projects/nexus-lab-tracker
tmp="$(mktemp -d)"
export DB_PATH="$tmp/lims.sqlite3"
export EXPORT_DIR="$tmp/exports"
mkdir -p "$EXPORT_DIR"
./scripts/lims.sh init
./scripts/migrate.sh up
./scripts/lims.sh container add --barcode TUBE-1 --kind tube --location bench-A
./scripts/lims.sh sample add --external-id S-001 --specimen-type saliva --container TUBE-1
# Human report
./scripts/lims.sh sample report --external-id S-001
# Snapshot export + verify (proves backup integrity)
./scripts/lims.sh snapshot export --exports-dir "$EXPORT_DIR" --include-sample S-001
./scripts/snapshot_verify.sh --artifact "$(ls -1t "$EXPORT_DIR"/snapshot_*.tar.gz | head -n 1)"
echo "OK: quickstart completed. Artifacts in: $tmp"
```
