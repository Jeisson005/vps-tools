#!/usr/bin/env bash
set -euo pipefail

echo "========================================================================"
echo "  HERMES AGENT, DASHBOARD & GATEWAY STATUS"
echo "========================================================================"

if command -v hermes &>/dev/null; then
  echo "[+] hermes CLI is available at $(which hermes)"
else
  echo "[-] hermes command not found in PATH"
fi

echo ""
echo "--> 1. Systemd Dashboard Service (hermes-dashboard.service):"
if systemctl is-active --quiet hermes-dashboard.service 2>/dev/null; then
  echo "[+] hermes-dashboard.service is ACTIVE and RUNNING"
  sudo systemctl status hermes-dashboard.service --no-pager | head -n 10
else
  echo "[-] hermes-dashboard.service is NOT running"
fi

echo ""
echo "--> 2. Systemd Gateway Service (hermes-gateway.service):"
if systemctl is-active --quiet hermes-gateway.service 2>/dev/null; then
  echo "[+] hermes-gateway.service is ACTIVE and RUNNING"
  sudo systemctl status hermes-gateway.service --no-pager | head -n 10
else
  echo "[-] hermes-gateway.service is NOT running"
fi

echo "========================================================================"
