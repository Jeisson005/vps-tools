#!/usr/bin/env bash
# ==============================================================================
# Start Portable Headscale Subnet Router / Exit Node / Bridge
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

mkdir -p state
chmod 700 state

if [[ -z "${TS_AUTHKEY:-}" ]]; then
  echo "[!] Warning: TS_AUTHKEY is empty."
  echo "    You can generate one on your Headscale server with: ./scripts/preauthkey.sh"
fi

echo "[+] Starting Tailscale Bridge Node (${NODE_HOSTNAME:-bridge-node})..."
docker compose up -d

echo "[+] Checking connection status..."
sleep 3
docker compose exec tailscale-node tailscale status || true

echo ""
echo "================================================================="
echo "✅ Headscale Node Started Successfully!"
echo "• Hostname:          ${NODE_HOSTNAME:-bridge-node}"
echo "• Server:            ${HEADSCALE_SERVER_URL:-https://headscale.jeisson.top}"
echo "• Advertised Routes: ${ADVERTISE_ROUTES:-(none)}"
echo "================================================================="
