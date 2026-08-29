#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${MCP_DIR}"

echo "========================================================================"
echo "  INSTALLING & DEPLOYING MCP GATEWAY (DOCKER COMPOSE)"
echo "========================================================================"

# 1. Initialize .env from .env.example if missing
if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    echo "--> .env not found. Creating from .env.example with secure random secrets..."
    cp .env.example .env
    
    # Generate secure random admin password
    ADMIN_PASS=$(openssl rand -base64 12 | tr -dc 'a-zA-Z0-9' | head -c 16)
    sed -i "s|change_this_to_a_secure_admin_password|${ADMIN_PASS}|g" .env
    
    # Generate random MCP client API key
    RAND_API_KEY="mcp_sec_$(openssl rand -hex 18)"
    sed -i "s|mcp_sec_replace_with_a_secure_token|${RAND_API_KEY}|g" .env

    # Generate random master encryption key
    RAND_MASTER=$(openssl rand -hex 32)
    sed -i "s|MCP_MASTER_KEY=|MCP_MASTER_KEY=${RAND_MASTER}|g" .env

    echo "[+] Generated random MCP_ADMIN_PASSWORD in .env"
    echo "[+] Generated random MCP_API_KEY in .env"
    echo "[+] Generated random MCP_MASTER_KEY in .env"
  else
    echo "[-] ERROR: Neither .env nor .env.example found." >&2
    exit 1
  fi
fi

# 2. Ensure data directory exists with strict permissions
mkdir -p data
chmod 700 data

# 3. Ensure Docker network exists
NGINX_NET="${NGINX_NETWORK:-nginx_default}"
if ! docker network inspect "${NGINX_NET}" &>/dev/null; then
  echo "--> Creating Docker network: ${NGINX_NET}..."
  docker network create "${NGINX_NET}"
fi

# 4. Build and start container
echo "--> Building and starting MCP Gateway container..."
docker compose up -d --build

echo ""
echo "--> Waiting for MCP Gateway to become healthy..."
sleep 3

if docker compose ps --status=running | grep -q "mcp-gateway"; then
  echo "[+] MCP Gateway container is RUNNING."
  docker compose ps
else
  echo "[-] ERROR: MCP Gateway failed to start." >&2
  docker compose logs --tail 30
  exit 1
fi

PORT=$(grep -E "^MCP_PORT=" .env | cut -d '=' -f2 || echo "8005")
DOMAIN=$(grep -E "^MCP_DOMAIN=" .env | cut -d '=' -f2 || echo "mcp.jeisson.top")

echo ""
echo "========================================================================"
echo "  MCP GATEWAY INSTALLED SUCCESSFULLY"
echo "  Local Port: http://127.0.0.1:${PORT}"
echo "  Admin Dashboard: http://127.0.0.1:${PORT}/admin (o https://${DOMAIN})"
echo "  Passbolt MCP Subroute: http://127.0.0.1:${PORT}/passbolt"
echo "  Unified MCP Subroute:  http://127.0.0.1:${PORT}/unified"
echo "========================================================================"
