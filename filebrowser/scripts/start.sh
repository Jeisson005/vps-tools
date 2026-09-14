#!/usr/bin/env bash
# ==============================================================================
# Start Filebrowser Service
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(dirname "${SCRIPT_DIR}")"

cd "${MODULE_DIR}"

if [[ ! -f ".env" ]]; then
    "${SCRIPT_DIR}/install.sh"
fi

echo "[*] Starting Filebrowser container..."
docker compose --env-file .env up -d

echo ""
echo "================================================================="
set -a
# shellcheck disable=SC1091
source .env
set +a
echo "Filebrowser running:"
echo "• Local:    http://127.0.0.1:${FILEBROWSER_PORT:-8095}/"
echo "• Public:   https://${FILEBROWSER_DOMAIN:-files.your-domain.com}"
echo "• Alt:      https://${FILEBROWSER_ALT_DOMAIN:-filebrowser.your-domain.com}"
echo ""
echo "First start prints a one-time admin password in the logs:"
echo "  docker compose logs filebrowser 2>&1 | grep -i password"
echo "Default if no DB yet: admin / admin (change it in Settings -> Users)."
echo "Nginx layer uses the shared credentials in nginx/auth/.htpasswd."
echo "================================================================="
echo ""
"${SCRIPT_DIR}/status.sh"
