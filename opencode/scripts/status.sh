#!/usr/bin/env bash
set -euo pipefail

echo "========================================================================"
echo "  OPENCODE AI & WEB SERVICE STATUS"
echo "========================================================================"
echo "--> OpenCode CLI version:"
if command -v opencode &>/dev/null; then
  opencode --version || true
else
  echo "[-] opencode command not found in PATH"
fi

echo ""
echo "--> Systemd Service (opencode-web.service):"
systemctl status opencode-web.service --no-pager || true

echo ""
echo "--> Listening Ports:"
ss -tulpn | grep -E "4096|opencode" || true
echo "========================================================================"
