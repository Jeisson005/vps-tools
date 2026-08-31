#!/usr/bin/env bash
# ==============================================================================
# Stop RustDesk Server & Web Client Stack
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

echo "[+] Stopping RustDesk Server stack..."
docker compose down
echo "[+] RustDesk Server stopped."
