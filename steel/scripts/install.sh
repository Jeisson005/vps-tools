#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STEEL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${STEEL_DIR}"

echo "========================================================================"
echo "  INSTALLING & DEPLOYING STEEL BROWSER (DOCKER COMPOSE)"
echo "========================================================================"

# Validate .env exists
if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    echo "--> .env not found. Creating from .env.example..."
    cp .env.example .env
    # Generate random secure API key if placeholder
    RAND_KEY=$(openssl rand -hex 24)
    sed -i "s|your_secure_steel_api_key_here|${RAND_KEY}|g" .env
    echo "[+] Generated random STEEL_API_KEY in .env"
  else
    echo "[-] ERROR: Neither .env nor .env.example found." >&2
    exit 1
  fi
fi

# Create data directories
mkdir -p data/steel-cache

echo "--> Pulling latest Steel Browser Docker image..."
docker compose pull

echo "--> Starting Steel Browser container..."
docker compose up -d

echo ""
echo "--> Waiting for Steel Browser to become healthy..."
sleep 3

if docker compose ps --status=running | grep -q "steel"; then
  echo "[+] Steel Browser container is RUNNING."
  docker compose ps
else
  echo "[-] ERROR: Steel Browser failed to start." >&2
  docker compose logs --tail 30
  exit 1
fi

# Firewall configuration if UFW is active
if command -v ufw &>/dev/null && sudo ufw status 2>/dev/null | grep -qw "active"; then
  echo "--> Allowing Docker bridge subnets (172.16.0.0/12) to Steel ports..."
  sudo ufw allow from 172.16.0.0/12 to any port 3000 proto tcp comment "Docker to Steel Browser API" >/dev/null || true
  sudo ufw allow from 172.16.0.0/12 to any port 9223 proto tcp comment "Docker to Steel CDP" >/dev/null || true
fi

echo ""
echo "========================================================================"
echo "  STEEL BROWSER INSTALLED SUCCESSFULLY"
echo "  REST API & Live UI: http://127.0.0.1:3000"
echo "  CDP WebSocket Port: 9223"
echo "========================================================================"
