#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

SERVICE_NAME="${SERVICE_NAME:-bash-mcp-http}"

echo "==> Service Status for '$SERVICE_NAME':"
systemctl status "$SERVICE_NAME" --no-pager || true

echo ""
echo "==> Recent Journal Logs:"
journalctl -u "$SERVICE_NAME" -n 20 --no-pager || true
