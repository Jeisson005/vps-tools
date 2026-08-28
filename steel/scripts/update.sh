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

echo "[*] Applying and validating security patches..."
python3 "${SCRIPT_DIR}/patch-steel.py"

echo "================================================================="
echo "[+] Steel Browser updated and protected successfully!"
echo "================================================================="
