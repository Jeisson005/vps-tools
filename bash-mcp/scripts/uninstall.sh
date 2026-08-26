#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Uninstalling host-native Bash-MCP service..."

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

SERVICE_NAME="${SERVICE_NAME:-bash-mcp-http}"

# 1. Stop and disable systemd service
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null || [[ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]]; then
  echo "--> Stopping and disabling systemd service..."
  systemctl stop "$SERVICE_NAME" 2>/dev/null || true
  systemctl disable "$SERVICE_NAME" 2>/dev/null || true
  rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
  systemctl daemon-reload
fi

# 2. Remove wrapper binaries
echo "--> Removing wrapper binaries..."
rm -f /usr/local/bin/bash-server /usr/local/bin/bash-mcp-app

# 3. Uninstall npm packages (optional)
if command -v npm &>/dev/null; then
  echo "--> Uninstalling npm global packages..."
  npm uninstall -g @nickw8/bash-mcp supergateway || true
fi

echo "==> Bash-MCP uninstalled successfully."
