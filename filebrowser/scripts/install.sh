#!/usr/bin/env bash
# ==============================================================================
# Filebrowser Installation & Setup Script
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(dirname "${SCRIPT_DIR}")"
ENV_FILE="${MODULE_DIR}/.env"
ENV_EXAMPLE="${MODULE_DIR}/.env.example"

echo "=== Setting up Filebrowser Module ==="

# 1. Ensure .env exists (untracked, holds no hardcoded secrets in git)
if [ ! -f "${ENV_FILE}" ]; then
    echo "[*] Creating .env from template..."
    cp "${ENV_EXAMPLE}" "${ENV_FILE}"
    chmod 600 "${ENV_FILE}"
    echo "[!] Edit ${ENV_FILE} (domains, port, PUID/PGID from 'id -u / id -g')."
else
    chmod 600 "${ENV_FILE}" || true
fi

# 2. Load variables for directory ownership
set -a
# shellcheck disable=SC1091
source "${ENV_FILE}"
set +a

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

# 3. Create persistent directories (gitignored runtime data)
mkdir -p "${MODULE_DIR}/data/srv" "${MODULE_DIR}/data/database" "${MODULE_DIR}/data/config"
chmod 755 "${MODULE_DIR}/data" "${MODULE_DIR}/data/srv" "${MODULE_DIR}/data/database" "${MODULE_DIR}/data/config"

# Fix ownership when running as root so the s6 image (abc user) can write
if [ "$EUID" -eq 0 ]; then
    chown -R "${PUID}:${PGID}" "${MODULE_DIR}/data" || true
fi

echo "[+] Data directories created:"
echo "    - Files:    ${MODULE_DIR}/data/srv"
echo "    - Database: ${MODULE_DIR}/data/database"
echo "    - Config:   ${MODULE_DIR}/data/config"
echo "[+] Configuration ready at: ${ENV_FILE}"
echo "=== Setup complete! Run './scripts/start.sh' to start Filebrowser ==="
