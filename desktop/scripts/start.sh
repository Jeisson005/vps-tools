#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a; source .env; set +a
elif [[ -f .env.example ]]; then
  set -a; source .env.example; set +a
fi

DESKTOP_USER="${DESKTOP_USER:-jeisson}"

echo "--> Starting Remote Desktop services (KasmVNC + XRDP)..."
sudo systemctl start "kasmvnc@${DESKTOP_USER}"
sudo systemctl start xrdp

echo "--> Services started."
sudo systemctl status "kasmvnc@${DESKTOP_USER}" --no-pager || true
