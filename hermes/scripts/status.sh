#!/usr/bin/env bash
set -euo pipefail

echo "========================================================================"
echo "  HERMES AGENT & DASHBOARD STATUS"
echo "========================================================================"

if command -v hermes &>/dev/null; then
  echo "[+] hermes CLI is available at $(which hermes)"
  echo "    Version / Help:"
  hermes --version 2>/dev/null || echo "    hermes command ready"
else
  echo "[-] hermes command not found in PATH"
fi

echo ""
echo "--> Systemd Service Status (hermes-dashboard.service):"
if systemctl is-active --quiet hermes-dashboard.service 2>/dev/null; then
  echo "[+] hermes-dashboard.service is ACTIVE and RUNNING"
  sudo systemctl status hermes-dashboard.service --no-pager | head -n 12
else
  echo "[-] hermes-dashboard.service is NOT running"
fi

echo "========================================================================"
