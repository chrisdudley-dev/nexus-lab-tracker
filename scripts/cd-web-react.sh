#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)/frontend/app"
exec "${SHELL:-/bin/bash}"
