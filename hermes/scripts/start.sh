#!/usr/bin/env bash
set -euo pipefail

echo "--> Starting Hermes services (dashboard & gateway)..."
sudo systemctl start hermes-dashboard.service || true
sudo systemctl start hermes-gateway.service || true
echo "[+] Hermes services started."
