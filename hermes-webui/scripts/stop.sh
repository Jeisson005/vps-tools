#!/usr/bin/env bash
# ==============================================================================
# Stop Hermes WebUI Sofia (host-native systemd service)
# ==============================================================================

set -euo pipefail

echo "[+] Stopping hermes-webui ..."
sudo systemctl stop hermes-webui.service
echo "[+] Hermes WebUI Sofia stopped."
