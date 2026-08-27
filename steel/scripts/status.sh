#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

echo "========================================================================"
echo "  STEEL BROWSER STATUS"
echo "========================================================================"

docker compose ps
echo ""
echo "--> Resource Consumption:"
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}" | grep -E "NAME|steel" || true
echo "========================================================================"
