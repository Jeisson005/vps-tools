#!/usr/bin/env bash
set -euo pipefail

echo "--> Stopping hermes-dashboard.service..."
sudo systemctl stop hermes-dashboard.service
echo "[+] Hermes Web Dashboard stopped."
