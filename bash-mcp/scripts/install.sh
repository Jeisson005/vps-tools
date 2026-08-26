#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Installing host-native Bash-MCP service..."

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

# Load .env if present
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
elif [[ -f .env.example ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.example
  set +a
fi

MCP_PORT="${MCP_PORT:-8001}"
MCP_BIND="${MCP_BIND:-127.0.0.1}"
BASH_MCP_MODE="${BASH_MCP_MODE:-off}"
SERVICE_USER="${SERVICE_USER:-root}"
SERVICE_NAME="${SERVICE_NAME:-bash-mcp-http}"
# Idle session lifetime (ms). Stateful mode reuses one child MCP process per
# session instead of forking (and leaking) one per HTTP request.
MCP_SESSION_TIMEOUT="${MCP_SESSION_TIMEOUT:-1800000}"

# 1. Check / Install Node.js and npm
if ! command -v node &>/dev/null || ! command -v npm &>/dev/null; then
  echo "--> Node.js/npm not found. Installing via apt..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y nodejs npm
fi

echo "--> Node.js version: $(node -v)"
echo "--> npm version: $(npm -v)"

# 2. Install @nickw8/bash-mcp and supergateway globally
echo "--> Installing @nickw8/bash-mcp and supergateway npm packages..."
npm install -g @nickw8/bash-mcp@^3.0.0 supergateway@^3.4.3

# 3. Create host wrapper scripts
echo "--> Setting up host CLI wrapper scripts..."

# Find npm global bin directory
NPM_GLOBAL_BIN="$(npm root -g)/@nickw8/bash-mcp/dist/index.js"
NODE_BIN="$(command -v node)"

# /usr/local/bin/bash-mcp (defaults to readOnly)
cat <<EOF > /usr/local/bin/bash-mcp-app
#!/bin/sh
exec env BASH_MCP_MODE=\${BASH_MCP_MODE:-readOnly} "$NODE_BIN" "$NPM_GLOBAL_BIN" "\$@"
EOF
chmod +x /usr/local/bin/bash-mcp-app

# /usr/local/bin/bash-server (full mode)
cat <<EOF > /usr/local/bin/bash-server
#!/bin/sh
exec env BASH_MCP_MODE=off "$NODE_BIN" "$NPM_GLOBAL_BIN" "\$@"
EOF
chmod +x /usr/local/bin/bash-server

# Link standard bash-mcp if not present
if [[ ! -e /usr/local/bin/bash-mcp ]]; then
  ln -s /usr/local/bin/bash-mcp-app /usr/local/bin/bash-mcp
fi

# 4. Create systemd service for HTTP transport (supergateway)
echo "--> Creating systemd service: /etc/systemd/system/${SERVICE_NAME}.service..."

TARGET_CMD="bash-server"
if [[ "$BASH_MCP_MODE" == "readOnly" ]]; then
  TARGET_CMD="bash-mcp-app"
fi

cat <<EOF > "/etc/systemd/system/${SERVICE_NAME}.service"
[Unit]
Description=Bash MCP HTTP endpoint via supergateway (Host Native)
After=network.target

[Service]
Type=simple
Environment=BASH_MCP_MODE=${BASH_MCP_MODE}
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment=HOME=/root
ExecStart=$(command -v supergateway) --stdio "${TARGET_CMD}" --outputTransport streamableHttp --port ${MCP_PORT} --host ${MCP_BIND} --stateful --sessionTimeout ${MCP_SESSION_TIMEOUT} --logLevel info
Restart=on-failure
RestartSec=3
User=${SERVICE_USER}
WorkingDirectory=/root

# Guardrails. Each MCP session is a node child of ~85 MB; a handful is normal.
# These cap the blast radius if a future transport regression starts leaking
# child processes again instead of letting it consume the whole box.
TasksMax=512
MemoryHigh=768M
MemoryMax=1G

[Install]
WantedBy=multi-user.target
EOF

# 5. Configure firewall for internal Docker bridge access if UFW is active
if command -v ufw &>/dev/null && ufw status | grep -qw "active"; then
  echo "--> Allowing Docker bridge subnets (172.16.0.0/12) to access port ${MCP_PORT} in UFW..."
  ufw allow from 172.16.0.0/12 to any port "${MCP_PORT}" proto tcp comment "Docker to Bash-MCP" >/dev/null || true
fi

# 6. Enable and start service
echo "--> Reloading systemd and enabling service..."
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

sleep 2
systemctl status "${SERVICE_NAME}" --no-pager || true

echo ""
echo "==> Bash-MCP successfully installed on host at http://${MCP_BIND}:${MCP_PORT}/mcp"
