#!/usr/bin/env bash
# ==============================================================================
# Stop Filebrowser Service
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(dirname "${SCRIPT_DIR}")"

cd "${MODULE_DIR}"
echo "[*] Stopping Filebrowser container..."
docker compose down

echo "[+] Filebrowser stopped."
