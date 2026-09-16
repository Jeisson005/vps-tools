#!/usr/bin/env bash
# ==============================================================================
# Start Hermes WebUI (community web client for Hermes Agent)
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

if [[ ! -f ".env" ]]; then
  echo "[!] .env not found, creating from .env.example..."
  cp .env.example .env
  chmod 600 .env
fi

# shellcheck disable=SC1091
set -a; source .env; set +a

# Password is mandatory when exposed through nginx — generate once if empty
if [[ -z "${HERMES_WEBUI_PASSWORD:-}" ]]; then
  HERMES_WEBUI_PASSWORD="$(openssl rand -hex 16)"
  echo "[+] Generated WebUI password, storing in .env ..."
  if grep -q "^HERMES_WEBUI_PASSWORD=" .env; then
    sed -i "s|^HERMES_WEBUI_PASSWORD=.*|HERMES_WEBUI_PASSWORD=${HERMES_WEBUI_PASSWORD}|" .env
  else
    echo "HERMES_WEBUI_PASSWORD=${HERMES_WEBUI_PASSWORD}" >> .env
  fi
  chmod 600 .env
fi

mkdir -p "${HERMES_WORKSPACE_DIR:-/home/jeisson/workspace}"

# Check & configure UFW rules if UFW is installed (loopback only — no ports needed)
echo "[+] Starting Hermes WebUI..."
docker compose up -d hermes-webui

echo "[+] Waiting for /health ..."
for _i in $(seq 1 30); do
  if curl -sf --max-time 3 "http://127.0.0.1:${HERMES_WEBUI_PORT:-8787}/health" >/dev/null 2>&1; then
    echo "[+] Hermes WebUI healthy."
    break
  fi
  sleep 2
  if [[ "${_i}" == "30" ]]; then
    echo "[!] WebUI did not become healthy — check: docker logs hermes-webui" >&2
  fi
done

echo ""
echo "================================================================="
echo "✅ Hermes WebUI Running!"
echo "• Local:    http://127.0.0.1:${HERMES_WEBUI_PORT:-8787}"
echo "• Public:   https://${HERMES_WEBUI_DOMAIN:-chat.jeisson.top} (via nginx)"
echo "• Password: (stored in hermes-webui/.env as HERMES_WEBUI_PASSWORD)"
echo "================================================================="
