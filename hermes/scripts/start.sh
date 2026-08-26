#!/usr/bin/env bash
set -euo pipefail

echo "--> Starting hermes-dashboard.service..."
sudo systemctl start hermes-dashboard.service
echo "[+] Hermes Web Dashboard started."
