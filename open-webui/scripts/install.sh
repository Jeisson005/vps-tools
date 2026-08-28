#!/usr/bin/env bash
# ==============================================================================
# Open WebUI Installation & Setup Script
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(dirname "${SCRIPT_DIR}")"
ENV_FILE="${MODULE_DIR}/.env"
ENV_EXAMPLE="${MODULE_DIR}/.env.example"

echo "=== Setting up Open WebUI Module ==="

# 1. Ensure .env exists
if [ ! -f "${ENV_FILE}" ]; then
    echo "[*] Creating .env from template..."
    cp "${ENV_EXAMPLE}" "${ENV_FILE}"
fi

# 2. Generate secure random secret key if missing
CURRENT_SECRET=$(grep -E "^WEBUI_SECRET_KEY=" "${ENV_FILE}" | cut -d '=' -f2- | tr -d '"' | tr -d "'" || true)
if [ -z "${CURRENT_SECRET}" ]; then
    echo "[*] Generating random 32-byte WEBUI_SECRET_KEY..."
    GENERATED_SECRET=$(openssl rand -hex 32)
    sed -i "s|^WEBUI_SECRET_KEY=.*|WEBUI_SECRET_KEY=${GENERATED_SECRET}|" "${ENV_FILE}"
fi

# 3. Create persistent directories
DATA_DIR="${MODULE_DIR}/data/open-webui"
WORKSPACE_DIR="${MODULE_DIR}/data/workspace"

mkdir -p "${DATA_DIR}" "${WORKSPACE_DIR}"
chmod -R 775 "${MODULE_DIR}/data"

echo "[+] Data directories created:"
echo "    - Storage:   ${DATA_DIR}"
echo "    - Workspace: ${WORKSPACE_DIR}"
echo "[+] Configuration ready at: ${ENV_FILE}"
echo "=== Setup complete! Run './scripts/start.sh' to start Open WebUI ==="
