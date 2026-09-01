#!/usr/bin/env bash
# ==============================================================================
# Show Headscale Status, Registered Nodes, and Routes
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

echo "=== Headscale Containers Status ==="
docker compose ps
echo ""

if docker compose ps headscale | grep -q "Up"; then
  echo "=== Headscale Users ==="
  docker compose exec headscale headscale users list || true
  echo ""

  echo "=== Registered Nodes (Machines) ==="
  docker compose exec headscale headscale nodes list || true
  echo ""

  echo "=== Subnets & Exit Routes ==="
  docker compose exec headscale headscale routes list || true
  echo ""

  echo "=== Pre-Auth Keys ==="
  DEFAULT_USER="${HEADSCALE_DEFAULT_USER:-jeisson}"
  docker compose exec headscale headscale preauthkeys list --user "${DEFAULT_USER}" || true
else
  echo "[!] Headscale core container is not running."
fi
