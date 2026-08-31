#!/usr/bin/env bash
set -euo pipefail

echo "[*] Stopping Sentinel service..."
sudo systemctl stop sentinel.service
echo "[+] Sentinel service stopped."
