#!/usr/bin/env bash
set -euo pipefail

# Snapshot commands dispatcher (export / restore / verify / doctor)
if [[ "${1:-}" == "snapshot" ]]; then
  shift || true
  sub="${1:-}"
  if [[ -z "$sub" || "$sub" == "-h" || "$sub" == "--help" ]]; then
    echo "Usage: ./scripts/lims.sh snapshot <export|restore|verify|doctor> [args]"
    echo "Try:   ./scripts/lims.sh snapshot export -h"
    exit 0
  fi
  case "$sub" in
    export)
      shift || true
      include_samples=()
      # API hook: sample IDs via env var so the API doesn't put untrusted input on argv.
      if [[ -n "${NEXUS_API_INCLUDE_SAMPLES:-}" ]]; then
        while IFS= read -r sid; do
          sid="${sid//$'\r'/}"  # tolerate CRLF
          # trim leading/trailing whitespace
          sid="${sid#"${sid%%[![:space:]]*}"}"
          sid="${sid%"${sid##*[![:space:]]}"}"
          [[ -n "$sid" ]] || continue
          [[ "$sid" =~ ^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$ ]] || { echo "ERROR: invalid sample id in NEXUS_API_INCLUDE_SAMPLES: $sid" >&2; exit 2; }
          include_samples+=("$sid")
          (( ${#include_samples[@]} <= 512 )) || { echo "ERROR: too many include samples (max 512)" >&2; exit 2; }
        done <<<"${NEXUS_API_INCLUDE_SAMPLES}"
      fi
      unset NEXUS_API_INCLUDE_SAMPLES || true

        json=0
      # Avoid stale state: snapshot includes should be driven ONLY by CLI args.
      unset SNAPSHOT_INCLUDE_SAMPLES SNAPSHOT_JSON || true

      while [[ $# -gt 0 ]]; do
        case "$1" in
          --exports-dir|--exports|--out)
            [[ $# -ge 2 ]] || { echo "ERROR: $1 requires a value" >&2; exit 2; }
            export EXPORTS_DIR="$2"
            shift 2
            ;;
            --include-sample)
              [[ $# -ge 2 ]] || { echo "ERROR: $1 requires a value" >&2; exit 2; }
              s="$2"
              s="${s#"${s%%[![:space:]]*}"}"
              s="${s%"${s##*[![:space:]]}"}"
              [[ -n "$s" ]] || { echo "ERROR: --include-sample must not be blank" >&2; exit 2; }
              [[ "$s" != *[[:space:]]* ]] || { echo "ERROR: --include-sample must not contain spaces" >&2; exit 2; }
              include_samples+=("$s")
              shift 2
              ;;            --json)
              json=1
              shift
              ;;

          -h|--help)
            echo "Usage: ./scripts/lims.sh snapshot export [--exports-dir PATH] [--include-sample ID]... [--json]"
            exit 0
            ;;
          *)
            echo "ERROR: unknown arg for snapshot export: $1" >&2
            exit 2
            ;;
        esac
      done
        if (( json == 1 )); then
          export SNAPSHOT_JSON=1
        fi

      if declare -p include_samples >/dev/null 2>&1 && (( ${#include_samples[@]} > 0 )); then
        SNAPSHOT_INCLUDE_SAMPLES="$(printf '%s\n' "${include_samples[@]}")"
        export SNAPSHOT_INCLUDE_SAMPLES
      fi

      exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/snapshot_export.sh"
      ;;

    restore)
      shift || true
      force=0
      backup=0
      artifact=""
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --force)  force=1; shift ;;
          --backup) backup=1; shift ;;
          -h|--help)
            echo "Usage: ./scripts/lims.sh snapshot restore <snapshot.tar.gz|snapshot-dir> [--force] [--backup]"
            exit 0
            ;;
          *)
            if [[ -z "$artifact" ]]; then
              artifact="$1"; shift
            else
              echo "ERROR: unexpected arg for snapshot restore: $1" >&2
              exit 2
            fi
            ;;
        esac
      done
      [[ -n "$artifact" ]] || { echo "ERROR: missing snapshot artifact path" >&2; exit 2; }
      export SNAPSHOT_ARTIFACT="$artifact"
      export SNAPSHOT_FORCE="$force"
      export SNAPSHOT_BACKUP="$backup"
      exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/snapshot_restore.sh"
      ;;

    verify)
      shift || true
      artifact=""
      do_migrate=1
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --no-migrate) do_migrate=0; shift ;;
          -h|--help)
            echo "Usage: ./scripts/lims.sh snapshot verify <snapshot.tar.gz|snapshot-dir|lims.sqlite3> [--no-migrate]"
            exit 0
            ;;
          *)
            if [[ -z "$artifact" ]]; then
              artifact="$1"; shift
            else
              echo "ERROR: unexpected arg for snapshot verify: $1" >&2
              exit 2
            fi
            ;;
        esac
      done
      [[ -n "$artifact" ]] || { echo "ERROR: missing snapshot artifact path" >&2; exit 2; }
      export SNAPSHOT_ARTIFACT="$artifact"
      export SNAPSHOT_DO_MIGRATE="$do_migrate"
      exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/snapshot_verify.sh"
      ;;

    doctor)
      shift || true
      if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
        echo "Usage: ./scripts/lims.sh snapshot doctor <snapshot.tar.gz|snapshot-dir|lims.sqlite3> [--no-migrate] [--json-only]"
        exit 0
      fi
      exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/snapshot_doctor.py" "$@"
      ;;

    diff)
      shift || true
      if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
        echo "Usage: ./scripts/lims.sh snapshot diff <A> <B> [--no-migrate] [--json-only]"
        exit 0
      fi
      exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/snapshot_diff.py" "$@"
      ;;

    latest)
      shift || true
      exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/snapshot_latest.sh" "$@"
      ;;

    diff-latest)
      shift || true
      exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/snapshot_diff_latest.sh" "$@"
      ;;

    pins)
      shift || true
      exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/snapshot_pins.sh" "$@"
      ;;
    pin)
      shift || true
      exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/snapshot_pin.sh" "$@"
      ;;
    unpin)
      shift || true
      exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/snapshot_unpin.sh" "$@"
      ;;
    prune)
      shift || true
      exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/snapshot_prune.sh" "$@"
      ;;

    gc)
      shift || true
      exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/snapshot_gc.sh" "$@"
      ;;

    *)
      echo "ERROR: unknown snapshot subcommand: ${sub:-<missing>}" >&2
      echo "HINT: try: ./scripts/lims.sh snapshot export" >&2
      echo "      or:  ./scripts/lims.sh snapshot restore <artifact> [--force] [--backup]" >&2
      echo "      or:  ./scripts/lims.sh snapshot verify  <artifact> [--no-migrate]" >&2
      echo "      or:  ./scripts/lims.sh snapshot doctor  <artifact> [--no-migrate] [--json-only]" >&2
      exit 2
      ;;
  esac
fi

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/env.sh"
exec python3 -m lims.cli "$@"
