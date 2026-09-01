#!/usr/bin/env bash
# ==============================================================================
# Show Tailscale Node Status & Active Routes
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

if docker compose ps | grep -q "Up"; then
  echo "=== Tailscale Local Node Status ==="
  docker compose exec tailscale-node tailscale status
  echo ""
  echo "=== Active IP & Peers ==="
  docker compose exec tailscale-node tailscale ip -4 || true
  docker compose exec tailscale-node tailscale ip -6 || true
  echo ""
  echo "=== Tailscale Netcheck (Latency & DERP) ==="
  docker compose exec tailscale-node tailscale netcheck || true
else
  echo "[!] Tailscale node container is not running."
fi
