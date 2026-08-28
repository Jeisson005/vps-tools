#!/usr/bin/env bash
# ==============================================================================
# Stop Open WebUI Service
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(dirname "${SCRIPT_DIR}")"

cd "${MODULE_DIR}"
echo "[*] Stopping Open WebUI container..."
docker compose down

echo "[+] Open WebUI stopped."
