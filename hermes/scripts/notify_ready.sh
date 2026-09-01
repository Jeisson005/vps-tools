#!/usr/bin/env bash
# ==============================================================================
# Hermes Gateway - Startup Notification Script
# Sends an alert via Telegram when Hermes Gateway starts successfully.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASE_DIR="$(cd "${HERMES_DIR}/.." && pwd)"

# Give gateway sockets and messaging bridges 4 seconds to settle
sleep 4

# Load environment variables from hermes/.env, sentinel/.env, or backup/.env
TOKEN=""
CHAT_ID=""
STARTUP_NOTIFICATION="true"

load_env() {
  local env_file="$1"
  if [[ -f "$env_file" ]]; then
    while IFS='=' read -r key val || [[ -n "$key" ]]; do
      key="$(echo "$key" | xargs)"
      [[ -z "$key" || "$key" =~ ^# ]] && continue
      val="${val%\"}"
      val="${val#\"}"
      val="${val%\'}"
      val="${val#\'}"
      case "$key" in
        HERMES_STARTUP_NOTIFICATION) STARTUP_NOTIFICATION="$val" ;;
        TELEGRAM_BOT_TOKEN) [[ -z "$TOKEN" ]] && TOKEN="$val" ;;
        TELEGRAM_BOT_URGENT_TOKEN) [[ -z "$TOKEN" ]] && TOKEN="$val" ;;
        TELEGRAM_CHAT_ID) [[ -z "$CHAT_ID" ]] && CHAT_ID="$val" ;;
      esac
    done < "$env_file"
  fi
}

load_env "${HERMES_DIR}/.env"
load_env "${BASE_DIR}/sentinel/.env"
load_env "${BASE_DIR}/backup/.env"

# If notification is disabled, exit cleanly
if [[ "${STARTUP_NOTIFICATION}" == "false" || "${STARTUP_NOTIFICATION}" == "0" ]]; then
  exit 0
fi

# If tokens are missing, try extracting from ~/.hermes/config.yaml
if [[ -z "$CHAT_ID" && -f "${HOME:-/home/jeisson}/.hermes/config.yaml" ]]; then
  CHAT_ID="$(grep -A 5 "platforms:" "${HOME:-/home/jeisson}/.hermes/config.yaml" | grep -A 4 "telegram:" | grep "chat_id:" | head -n 1 | awk '{print $2}' | tr -d "'\"")"
fi

if [[ -z "$TOKEN" || -z "$CHAT_ID" ]]; then
  # No Telegram configuration found, skip without error
  exit 0
fi

HOST="$(hostname)"
DATE="$(date '+%Y-%m-%d %H:%M:%S')"
MSG="🟢 *Hermes Gateway Online* 🟢%0A%0A🖥️ *Host:* \`${HOST}\`%0A🤖 *Estado:* Gateway iniciado y listo para recibir mensajes.%0A📅 *Fecha:* \`${DATE}\`"

curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -d "chat_id=${CHAT_ID}" \
  -d "text=${MSG}" \
  -d "parse_mode=Markdown" >/dev/null 2>&1 || true

exit 0
