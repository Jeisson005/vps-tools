#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a; source .env; set +a
elif [[ -f .env.example ]]; then
  set -a; source .env.example; set +a
fi

DESKTOP_USER="${DESKTOP_USER:-jeisson}"

echo "--> Stopping Remote Desktop services..."
sudo systemctl stop "kasmvnc@${DESKTOP_USER}" || true
sudo systemctl stop xrdp || true
echo "--> Services stopped."
