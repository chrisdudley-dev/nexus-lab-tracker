#!/usr/bin/env bash
set -euo pipefail
fail(){ echo "ERROR: $*" >&2; exit 2; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

dir="${EXPORTS_DIR:-}"
pins_file=""
apply=0
verbose=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) [[ $# -ge 2 ]] || fail "--dir requires a value"; dir="$2"; shift 2 ;;
    --file) [[ $# -ge 2 ]] || fail "--file requires a value"; pins_file="$2"; shift 2 ;;
    --apply) apply=1; shift ;;
    --dry-run) apply=0; shift ;;
    -v|--verbose) verbose=1; shift ;;
    -h|--help)
      echo "Usage: ./scripts/lims.sh snapshot gc [--dir PATH] [--file PINS_FILE] [--apply] [--dry-run] [-v]"
      echo "  Finds orphan snapshot artifacts in exports dir:"
      echo "    - orphan tarball: snapshot-*.tar.gz/tgz with no matching snapshot dir"
      echo "    - orphan dir:     snapshot-* dir with no matching tarball"
      echo "  Default is dry-run. Use --apply to delete orphans."
      echo "  Pinned tarballs are never deleted (even if orphan)."
      exit 0 ;;
    *) fail "unknown arg: $1" ;;
  esac
done

# Resolve exports dir
if [[ -z "$dir" ]]; then
  [[ -d "$REPO_ROOT/exports" ]] || fail "EXPORTS_DIR not set and ./exports not found (use --dir PATH)"
  dir="$REPO_ROOT/exports"
fi
[[ "$dir" == /* ]] || dir="$REPO_ROOT/$dir"
[[ -d "$dir" ]] || fail "exports dir not found: $dir"

# Resolve pins file
if [[ -z "$pins_file" ]]; then
  pins_file="${SNAPSHOT_PINS_FILE:-$dir/.snapshot_pins}"
fi
[[ "$pins_file" == /* ]] || pins_file="$REPO_ROOT/$pins_file"

# Load pins into set
declare -A pinned=()
if [[ -f "$pins_file" ]]; then
  while IFS= read -r line; do
    line="${line%%#*}"
    line="$(echo "$line" | sed 's/[[:space:]]*$//')"
    [[ -n "$line" ]] || continue
    pinned["$line"]=1
  done < "$pins_file"
fi

# Collect tarballs + dirs
mapfile -t tars < <(
  find "$dir" -maxdepth 1 -type f \( -name 'snapshot-*.tar.gz' -o -name 'snapshot-*.tgz' \) -printf '%f\n' 2>/dev/null | sort -r
)
mapfile -t dirs < <(
  find "$dir" -maxdepth 1 -type d -name 'snapshot-*' -printf '%f\n' 2>/dev/null | sort -r
)

declare -A tar_set=()
declare -A dir_set=()

for f in "${tars[@]}"; do tar_set["$f"]=1; done
for d in "${dirs[@]}"; do dir_set["$d"]=1; done

# Orphans
orphan_tar=()
pinned_orphan_tar=()
orphan_dir=()

# Orphan tarballs: tar exists but matching dir missing
for f in "${tars[@]}"; do
  [[ "$f" != *"/"* ]] || fail "refusing suspicious tarball name (contains '/'): $f"
  base="$f"
  d="${base%.tar.gz}"
  d="${d%.tgz}"
  if [[ -z "${dir_set[$d]:-}" ]]; then
    if [[ -n "${pinned[$base]:-}" ]]; then
      pinned_orphan_tar+=("$base")
    else
      orphan_tar+=("$base")
    fi
  fi
done

# Orphan dirs: dir exists but no matching tarball
for d in "${dirs[@]}"; do
  [[ "$d" != *"/"* ]] || fail "refusing suspicious dir name (contains '/'): $d"
  tgz="$d.tgz"
  tgz2="$d.tar.gz"
  if [[ -z "${tar_set[$tgz]:-}" && -z "${tar_set[$tgz2]:-}" ]]; then
    orphan_dir+=("$d")
  fi
done

tar_del=${#orphan_tar[@]}
dir_del=${#orphan_dir[@]}
pin_orph=${#pinned_orphan_tar[@]}

if (( tar_del == 0 && dir_del == 0 && pin_orph == 0 )); then
  echo "OK: gc clean (no orphans found) in: $dir"
  exit 0
fi

echo "== Snapshot GC Report =="
echo "dir: $dir"
echo "pins_file: $pins_file"
echo "mode: $([[ $apply -eq 1 ]] && echo APPLY || echo DRY-RUN)"
echo "orphan_tarballs: $tar_del"
echo "orphan_dirs:     $dir_del"
echo "pinned_orphans:  $pin_orph"

if (( pin_orph > 0 )); then
  echo ""
  echo "Pinned orphan tarballs (kept):"
  for f in "${pinned_orphan_tar[@]}"; do
    echo "KEEP (pinned orphan): $dir/$f"
  done
fi

if (( tar_del > 0 )); then
  echo ""
  echo "Orphan tarballs:"
  for f in "${orphan_tar[@]}"; do
    echo "DELETE tarball: $dir/$f"
  done
fi

if (( dir_del > 0 )); then
  echo ""
  echo "Orphan dirs:"
  for d in "${orphan_dir[@]}"; do
    echo "DELETE dir:     $dir/$d"
  done
fi

if (( apply == 0 )); then
  echo ""
  echo "DRY-RUN: no files deleted."
  exit 0
fi

# Apply deletions
for f in "${orphan_tar[@]}"; do
  rm -f -- "$dir/$f"
done

for d in "${orphan_dir[@]}"; do
  rm -rf -- "$dir/$d"
done

echo ""
echo "OK: gc applied (deleted $tar_del tarball(s), $dir_del dir(s); kept $pin_orph pinned orphan(s))."
