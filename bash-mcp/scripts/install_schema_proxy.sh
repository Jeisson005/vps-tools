#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Installing MCP Schema-Sanitizing Compatibility Proxy..."

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

if [[ -f .env ]]; then
  set -a; source .env; set +a
elif [[ -f .env.example ]]; then
  set -a; source .env.example; set +a
fi

MCP_PORT="${MCP_PORT:-8001}"
PROXY_PORT="${SCHEMA_PROXY_PORT:-${GEMINI_PROXY_PORT:-8002}}"
PROXY_BIND="${SCHEMA_PROXY_BIND:-${GEMINI_PROXY_BIND:-0.0.0.0}}"
STRIP_OUTPUT="${SCHEMA_PROXY_STRIP_OUTPUT:-${GEMINI_PROXY_STRIP_OUTPUT:-1}}"
SERVICE_NAME="${SCHEMA_PROXY_SERVICE_NAME:-bash-mcp-schema-proxy}"
SERVICE_USER="${SERVICE_USER:-root}"

install -m 0755 schema_proxy.py /usr/local/bin/mcp-schema-proxy
echo "--> Installed /usr/local/bin/mcp-schema-proxy"

# Remove deprecated gemini proxy service if active
if systemctl is-active --quiet bash-mcp-gemini-proxy 2>/dev/null; then
  echo "--> Stopping legacy bash-mcp-gemini-proxy..."
  systemctl stop bash-mcp-gemini-proxy || true
  systemctl disable bash-mcp-gemini-proxy || true
  rm -f /etc/systemd/system/bash-mcp-gemini-proxy.service
fi

cat <<UNIT > "/etc/systemd/system/${SERVICE_NAME}.service"
[Unit]
Description=MCP Universal Schema-Sanitizing Compatibility Proxy
After=network.target ${BASH_MCP_SERVICE:-bash-mcp-http}.service
Wants=${BASH_MCP_SERVICE:-bash-mcp-http}.service

[Service]
Type=simple
Environment=SCHEMA_PROXY_BIND=${PROXY_BIND}
Environment=SCHEMA_PROXY_PORT=${PROXY_PORT}
Environment=SCHEMA_PROXY_UPSTREAM=http://127.0.0.1:${MCP_PORT}/mcp
Environment=SCHEMA_PROXY_STRIP_OUTPUT=${STRIP_OUTPUT}
ExecStart=$(command -v python3) /usr/local/bin/mcp-schema-proxy
Restart=on-failure
RestartSec=3
User=${SERVICE_USER}

[Install]
WantedBy=multi-user.target
UNIT

# Allow the Nginx container (docker bridge) to reach the proxy port
if command -v ufw &>/dev/null && ufw status | grep -qw "active"; then
  echo "--> Allowing Docker bridge subnets (172.16.0.0/12) to port ${PROXY_PORT} in UFW..."
  ufw allow from 172.16.0.0/12 to any port "${PROXY_PORT}" proto tcp comment "Docker to MCP Schema proxy" >/dev/null || true
fi

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"
sleep 1
systemctl status "${SERVICE_NAME}" --no-pager || true

echo ""
echo "==> MCP Schema proxy listening on http://${PROXY_BIND}:${PROXY_PORT}"
