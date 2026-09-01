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

# Load variables
set -a
# shellcheck disable=SC1091
source .env
set +a

mkdir -p data web-config/.config/rustdesk
chmod 755 data web-config

echo "[+] Starting RustDesk Server (hbbs & hbbr)..."
docker compose up -d hbbs hbbr

echo "[+] Waiting for hbbs to generate public key..."
PUB_KEY=""
for i in {1..15}; do
  if [[ -f "data/id_ed25519.pub" ]]; then
    PUB_KEY=$(cat data/id_ed25519.pub)
    break
  fi
  sleep 1
done

if [[ -n "${PUB_KEY}" ]]; then
  echo "[+] Pre-configuring web client with server key & rendezvous server..."
  cat << EOF > web-config/.config/rustdesk/RustDesk2.toml
[options]
custom-rendezvous-server = "${RUSTDESK_DOMAIN:-rustdesk.jeisson.top}"
relay-server = "${RUSTDESK_DOMAIN:-rustdesk.jeisson.top}"
key = "${PUB_KEY}"
allow-audio = "Y"
allow-clipboard = "Y"
allow-file-transfer = "Y"
allow-keyboard-mouse = "Y"
EOF
  chmod -R 777 web-config/.config
fi

echo "[+] Starting Web Client..."
docker compose up -d rustdesk-web

echo ""
echo "================================================================="
echo "✅ RustDesk Server & Web Client Running Successfully!"
echo "• ID Server:      ${RUSTDESK_DOMAIN:-rustdesk.jeisson.top}:21116"
echo "• Relay Server:   ${RUSTDESK_DOMAIN:-rustdesk.jeisson.top}:21117"
echo "• Server Pub Key: ${PUB_KEY}"
echo "• Web Client URL: https://${RUSTDESK_WEB_DOMAIN:-desk.jeisson.top}"
echo "================================================================="
