#!/usr/bin/env bash
# ==============================================================================
# Start Headscale Server & UI Stack
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

if [[ ! -f ".env" ]]; then
  echo "[!] .env file not found. Creating from .env.example..."
  cp .env.example .env
  chmod 600 .env
fi

# Load variables
set -a
# shellcheck disable=SC1091
source .env
set +a

mkdir -p data config /var/run/headscale
chmod 755 data config

# Generate config.yaml from template with environment variables substituted
export HEADSCALE_SERVER_URL="${HEADSCALE_SERVER_URL:-https://headscale.jeisson.top}"
export HEADSCALE_BASE_DOMAIN="${HEADSCALE_BASE_DOMAIN:-vpn.jeisson.top}"
export HEADSCALE_IP_PREFIX_V4="${HEADSCALE_IP_PREFIX_V4:-100.64.0.0/10}"
export HEADSCALE_IP_PREFIX_V6="${HEADSCALE_IP_PREFIX_V6:-fd7a:115c:a1e0::/48}"

envsubst < config/config.yaml.template > config/config.yaml
chmod 644 config/config.yaml

echo "[+] Starting Headscale Core..."
docker compose up -d headscale

echo "[+] Waiting for Headscale socket initialization..."
sleep 3

# Ensure default user/namespace exists
DEFAULT_USER="${HEADSCALE_DEFAULT_USER:-jeisson}"
if ! docker compose exec headscale headscale users list | grep -q "${DEFAULT_USER}"; then
  echo "[+] Creating default user/namespace: ${DEFAULT_USER}..."
  docker compose exec headscale headscale users create "${DEFAULT_USER}" || true
fi

echo "[+] Starting Headscale UI..."
docker compose up -d headscale-ui

echo ""
echo "================================================================="
echo "✅ Headscale Server & Web UI Running Successfully!"
echo "• Control Server: ${HEADSCALE_SERVER_URL}"
echo "• Base Domain:    ${HEADSCALE_BASE_DOMAIN}"
echo "• Default User:   ${DEFAULT_USER}"
echo "• UI Local Port:  127.0.0.1:8086"
echo "================================================================="
