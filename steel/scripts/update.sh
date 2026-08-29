#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Steel Browser Safe Update & Patch Manager
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STEEL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${STEEL_DIR}"

echo "================================================================="
echo "--> Updating Steel Browser container safely"
echo "================================================================="

echo "[*] Pulling latest Steel Browser image..."
docker compose pull

echo "[*] Recreating container with latest image..."
docker compose up -d

echo "================================================================="
echo "[+] Steel Browser updated successfully!"
echo "================================================================="
