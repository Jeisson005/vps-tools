#!/usr/bin/env bash
# ==============================================================================
# Stop Headscale Stack
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

echo "[+] Stopping Headscale and UI..."
docker compose down

echo "✅ Headscale stack stopped."
