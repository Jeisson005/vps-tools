#!/usr/bin/env bash
set -euo pipefail

echo "--> Stopping Hermes services (dashboard & gateway)..."
sudo systemctl stop hermes-dashboard.service || true
sudo systemctl stop hermes-gateway.service || true
echo "[+] Hermes services stopped."
