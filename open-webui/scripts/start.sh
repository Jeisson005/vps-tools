#!/usr/bin/env bash
# ==============================================================================
# Start Open WebUI Service
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(dirname "${SCRIPT_DIR}")"

cd "${MODULE_DIR}"
if [ ! -f .env ]; then
    "${SCRIPT_DIR}/install.sh"
fi

echo "[*] Starting Open WebUI container..."
chmod -R 777 "${MODULE_DIR}/data" 2>/dev/null || true
docker compose --env-file .env up -d

echo "[+] Open WebUI started successfully!"
"${SCRIPT_DIR}/status.sh"
