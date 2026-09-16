#!/usr/bin/env bash
# ==============================================================================
# Hermes WebUI Status
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

# shellcheck disable=SC1091
[[ -f .env ]] && set -a && source .env && set +a

docker compose ps
echo ""
curl -sf --max-time 5 "http://127.0.0.1:${HERMES_WEBUI_PORT:-8787}/health" >/dev/null 2>&1 \
  && echo "✅ /health OK" \
  || echo "[!] /health not responding"
