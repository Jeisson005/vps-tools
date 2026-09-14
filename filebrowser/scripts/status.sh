#!/usr/bin/env bash
# ==============================================================================
# Filebrowser Status & Health Check Script
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(dirname "${SCRIPT_DIR}")"

cd "${MODULE_DIR}"

echo "=== Filebrowser Status ==="
docker compose ps

echo -e "\n=== Resource Usage ==="
docker stats filebrowser --no-stream 2>/dev/null || echo "Container 'filebrowser' is not running."

echo -e "\n=== Health Endpoint Test ==="
PORT=$(grep -E "^FILEBROWSER_PORT=" .env 2>/dev/null | cut -d '=' -f2- | tr -d '"' | tr -d "'" || echo "8095")
PORT="${PORT:-8095}"
if curl -s -f "http://127.0.0.1:${PORT}/" > /dev/null; then
    echo "[+] Filebrowser is reachable on port ${PORT}"
else
    echo "[-] Filebrowser is not reachable on port ${PORT}"
fi
