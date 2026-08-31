#!/usr/bin/env bash
# ==============================================================================
# Start RustDesk Server & Web Client Stack
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

if [[ ! -f ".env" ]]; then
  echo "[!] .env file not found. Creating from .env.example..."
  cp .env.example .env
  chmod 600 .env
fi

mkdir -p data web-config
chmod 755 data web-config

echo "[+] Starting RustDesk Server (hbbs, hbbr, and web client)..."
docker compose up -d

echo ""
echo "[+] Waiting for hbbs to generate public key..."
for i in {1..10}; do
  if [[ -f "data/id_ed25519.pub" ]]; then
    PUB_KEY=$(cat data/id_ed25519.pub)
    echo "================================================================="
    echo "✅ RustDesk Server Started Successfully!"
    echo "• ID Server:      ${RUSTDESK_DOMAIN:-rustdesk.jeisson.top}:21116"
    echo "• Relay Server:   ${RUSTDESK_DOMAIN:-rustdesk.jeisson.top}:21117"
    echo "• Server Pub Key: ${PUB_KEY}"
    echo "• Web Client URL: https://${RUSTDESK_WEB_DOMAIN:-desk.jeisson.top}"
    echo "================================================================="
    exit 0
  fi
  sleep 1
done

echo "[+] RustDesk stack is running."
