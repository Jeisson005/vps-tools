#!/usr/bin/env bash
# ==============================================================================
# Helper to Enable / Disable Subnet Routes & Exit Nodes in Headscale
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

ACTION="${1:-list}"
ROUTE_ID="${2:-}"

case "${ACTION}" in
  enable)
    if [[ -z "${ROUTE_ID}" ]]; then
      echo "Usage: $0 enable <route-id>"
      exit 1
    fi
    echo "[+] Enabling route ID: ${ROUTE_ID}..."
    docker compose exec headscale headscale routes enable -r "${ROUTE_ID}"
    ;;
  disable)
    if [[ -z "${ROUTE_ID}" ]]; then
      echo "Usage: $0 disable <route-id>"
      exit 1
    fi
    echo "[+] Disabling route ID: ${ROUTE_ID}..."
    docker compose exec headscale headscale routes disable -r "${ROUTE_ID}"
    ;;
  list)
    echo "=== Advertised Routes & Exit Nodes ==="
    docker compose exec headscale headscale routes list
    ;;
  *)
    echo "Usage: $0 {list|enable|disable} [route-id]"
    exit 1
    ;;
esac
