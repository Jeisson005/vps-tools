#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

echo "--> Rebuilding MCP Gateway Docker image without cache..."
docker compose build --no-cache

echo "--> Restarting MCP Gateway container..."
docker compose up -d
docker compose ps
