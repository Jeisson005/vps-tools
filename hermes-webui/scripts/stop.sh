#!/usr/bin/env bash
# ==============================================================================
# Stop Hermes WebUI
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

echo "[+] Stopping Hermes WebUI..."
docker compose down
echo "[+] Hermes WebUI stopped."
