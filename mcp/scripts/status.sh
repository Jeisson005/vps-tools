#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

PORT=$(grep -E "^MCP_PORT=" .env 2>/dev/null | cut -d '=' -f2 || echo "8005")

echo "=== MCP Gateway Container Status ==="
docker compose ps

echo ""
echo "=== Health Endpoint Test ==="
if curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null; then
  curl -s "http://127.0.0.1:${PORT}/health" | (command -v jq &>/dev/null && jq . || cat)
  echo ""
  echo "[+] Healthcheck OK!"
else
  echo "[-] Could not connect to http://127.0.0.1:${PORT}/health"
fi

echo ""
echo "=== Recent Container Logs ==="
docker compose logs --tail=25
