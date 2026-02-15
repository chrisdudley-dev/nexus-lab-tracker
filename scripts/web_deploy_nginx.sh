#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="${REPO_ROOT}/frontend"
DIST_DIR="${WEB_DIR}/dist"
WEBROOT="/var/www/nexus-web-react"

echo "== Nexus Web Deploy (nginx) =="
echo "Repo:     ${REPO_ROOT}"
echo "Web dir:  ${WEB_DIR}"
echo "Webroot:  ${WEBROOT}"
echo

command -v npm >/dev/null 2>&1 || { echo "ERROR: npm not found"; exit 1; }
test -d "${WEB_DIR}" || { echo "ERROR: missing ${WEB_DIR}"; exit 1; }

echo "-> Build (Vite production build)"
cd "${WEB_DIR}"
npm run build

test -d "${DIST_DIR}" || { echo "ERROR: build did not produce dist/"; exit 1; }

echo
echo "-> Sync dist/ to nginx webroot (requires sudo)"
sudo mkdir -p "${WEBROOT}"
sudo rsync -a --delete "${DIST_DIR}/" "${WEBROOT}/"

echo
echo "-> Validate + reload nginx"
sudo nginx -t
sudo systemctl reload nginx

echo
echo "OK: deployed UI to ${WEBROOT} (served on :8788)"
