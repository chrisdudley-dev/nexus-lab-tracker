#!/usr/bin/env bash
set -euo pipefail

# ---- Model 1: snapshot export passthrough ---------------------------------
if [[ "${1:-}" == "snapshot" ]]; then
  shift || true
  sub="${1:-}"
  case "$sub" in
    export)
      shift || true
      # Optional: allow overriding export output dir
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --exports-dir|--exports|--out)
            [[ $# -ge 2 ]] || { echo "ERROR: $1 requires a value" >&2; exit 2; }
            export EXPORTS_DIR="$2"
            shift 2
            ;;
          -h|--help)
            echo "Usage: ./scripts/lims.sh snapshot export [--exports-dir PATH]" 
            exit 0
            ;;
          *)
            echo "ERROR: unknown arg for snapshot export: $1" >&2
            exit 2
            ;;
        esac
      done
      exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/snapshot_export.sh"
      ;;
    *)
      echo "ERROR: unknown snapshot subcommand: ${sub:-<missing>}" >&2
      echo "HINT: try: ./scripts/lims.sh snapshot export" >&2
      exit 2
      ;;
  esac
fi
# ---------------------------------------------------------------------------
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/env.sh"
exec python3 -m lims.cli "$@"
