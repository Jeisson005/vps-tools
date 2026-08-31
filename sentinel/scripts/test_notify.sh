#!/usr/bin/env bash
# ==============================================================================
# Sentinel - Telegram Notification Tester
# Sends a verification ping to confirm bot tokens and chat ID are working.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${BASE_DIR}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[-] ERROR: Configuration file not found at ${ENV_FILE}" >&2
  echo "    Please copy ${BASE_DIR}/.env.example to ${ENV_FILE} and configure it." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"

TOKEN="${TELEGRAM_BOT_URGENT_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"

if [[ -z "${TOKEN}" || -z "${TELEGRAM_CHAT_ID:-}" ]]; then
  echo "[-] ERROR: Telegram bot token or TELEGRAM_CHAT_ID not configured in ${ENV_FILE}" >&2
  exit 1
fi

echo "[+] Sending test notification to Telegram (Chat ID: ${TELEGRAM_CHAT_ID})..."

RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  -d "text=🛡️ *VPS Tools Sentinel - Notificación de Prueba*%0A%0A✅ Conexión verificada exitosamente.%0A🖥️ *Host:* \`$(hostname)\`%0A📅 *Fecha:* \`$(date -R)\`%0A📊 *Estado:* Sistema Sentinel activo y listo." \
  -d "parse_mode=Markdown")

if echo "${RESPONSE}" | grep -q '"ok":true'; then
  echo "[+] ✓ Telegram notification delivered successfully!"
else
  echo "[-] ❌ Telegram API returned an error:" >&2
  echo "${RESPONSE}" >&2
  exit 1
fi
