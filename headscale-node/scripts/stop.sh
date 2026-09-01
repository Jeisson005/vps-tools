#!/usr/bin/env bash
# ==============================================================================
# Stop Headscale Bridge Node
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

echo "[+] Stopping Tailscale Bridge Node..."
docker compose down

echo "✅ Tailscale node stopped."
