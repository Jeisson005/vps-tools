#!/usr/bin/env bash
# ==============================================================================
# Open WebUI Status & Health Check Script
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(dirname "${SCRIPT_DIR}")"

cd "${MODULE_DIR}"
echo "=== Open WebUI Status ==="
docker compose ps

echo -e "\n=== Resource Usage ==="
docker stats open-webui --no-stream 2>/dev/null || echo "Container 'open-webui' is not running."

echo -e "\n=== Health Endpoint Test ==="
PORT=$(grep -E "^OPEN_WEBUI_PORT=" .env 2>/dev/null | cut -d '=' -f2- | tr -d '"' | tr -d "'" || echo "8080")
PORT="${PORT:-8080}"
curl -s -f "http://127.0.0.1:${PORT}/health" && echo -e "\n[+] Open WebUI Health Endpoint: OK" || echo -e "\n[-] Open WebUI is not reachable on port ${PORT}"
