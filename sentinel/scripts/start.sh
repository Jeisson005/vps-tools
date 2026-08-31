#!/usr/bin/env bash
set -euo pipefail

echo "[*] Starting Sentinel service..."
sudo systemctl start sentinel.service
echo "[+] Sentinel service started."
