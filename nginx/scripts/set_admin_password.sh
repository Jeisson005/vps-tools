#!/usr/bin/env bash
# ==============================================================================
# Set / Rotate Admin Password for All Nginx-Protected Services
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
AUTH_DIR="${REPO_DIR}/nginx/auth"
HTPASSWD_FILE="${AUTH_DIR}/.htpasswd"

USER_NAME="${1:-jeisson}"
PASSWORD="${2:-}"

if [[ -z "${PASSWORD}" ]]; then
  read -rsp "Enter new admin password for user '${USER_NAME}': " PASSWORD
  echo ""
fi

if [[ -z "${PASSWORD}" ]]; then
  echo "[-] Password cannot be empty." >&2
  exit 1
fi

mkdir -p "${AUTH_DIR}"
chmod 755 "${AUTH_DIR}"

HASHED_PASS=$(openssl passwd -apr1 "${PASSWORD}")
echo "${USER_NAME}:${HASHED_PASS}" > "${HTPASSWD_FILE}"
chmod 644 "${HTPASSWD_FILE}"

echo "[+] Successfully updated ${HTPASSWD_FILE} for user '${USER_NAME}'."

# Reload nginx if running
if command -v docker >/dev/null 2>&1; then
  if docker ps --format '{{.Names}}' | grep -q "^nginx-core-1$"; then
    docker exec nginx-core-1 nginx -s reload 2>/dev/null && echo "[+] Nginx configuration reloaded." || true
  fi
fi
