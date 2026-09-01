#!/usr/bin/env bash
# ==============================================================================
# Hermes Gateway - Startup Notification Script
# Sends notification to Telegram (Hermes Bot) and WhatsApp (Baileys Bridge)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
HERMES_HOME="${HOME:-/home/jeisson}"

# Wait up to 10 seconds for Hermes messaging bridges to establish connection
sleep 5

TOKEN=""
CHAT_ID=""
WA_CHAT_ID=""
WA_PORT="3005"
STARTUP_NOTIFICATION="true"

# 1. Read Hermes personal configuration from ~/.hermes/.env
if [[ -f "${HERMES_HOME}/.hermes/.env" ]]; then
  while IFS='=' read -r key val || [[ -n "$key" ]]; do
    key="$(echo "$key" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    [[ -z "$key" || "$key" =~ ^# ]] && continue
    val="${val%\"}"
    val="${val#\"}"
    val="${val%\'}"
    val="${val#\'}"
    case "$key" in
      TELEGRAM_BOT_TOKEN) [[ -z "$TOKEN" ]] && TOKEN="$val" ;;
      TELEGRAM_ALLOWED_USERS) [[ -z "$CHAT_ID" ]] && CHAT_ID="${val%%,*}" ;;
      WHATSAPP_HOME_CHANNEL) [[ -z "$WA_CHAT_ID" ]] && WA_CHAT_ID="$val" ;;
      WHATSAPP_ALLOWED_USERS) [[ -z "$WA_CHAT_ID" ]] && WA_CHAT_ID="${val%%,*}" ;;
    esac
  done < "${HERMES_HOME}/.hermes/.env"
fi

# Fallback: check config.yaml
if [[ -f "${HERMES_HOME}/.hermes/config.yaml" ]]; then
  if [[ -z "$CHAT_ID" ]]; then
    CHAT_ID="$(grep -A 5 "telegram:" "${HERMES_HOME}/.hermes/config.yaml" | grep "chat_id:" | head -n 1 | awk '{print $2}' | tr -d "'\"")"
  fi
  if [[ -z "$WA_CHAT_ID" ]]; then
    WA_CHAT_ID="$(grep -A 5 "whatsapp:" "${HERMES_HOME}/.hermes/config.yaml" | grep "chat_id:" | head -n 1 | awk '{print $2}' | tr -d "'\"")"
  fi
fi

# Check optional enable/disable in vps-tools/hermes/.env
if [[ -f "${HERMES_DIR}/.env" ]]; then
  while IFS='=' read -r key val || [[ -n "$key" ]]; do
    key="$(echo "$key" | xargs)"
    [[ -z "$key" || "$key" =~ ^# ]] && continue
    val="${val%\"}"
    val="${val#\"}"
    val="${val%\'}"
    val="${val#\'}"
    if [[ "$key" == "HERMES_STARTUP_NOTIFICATION" ]]; then
      STARTUP_NOTIFICATION="$val"
    fi
  done < "${HERMES_DIR}/.env"
fi

if [[ "${STARTUP_NOTIFICATION}" == "false" || "${STARTUP_NOTIFICATION}" == "0" ]]; then
  exit 0
fi

HOST="$(hostname)"
DATE="$(date '+%Y-%m-%d %H:%M:%S')"
MSG_TELEGRAM="🟢 *Hermes Gateway Online* 🟢%0A%0A🖥️ *Host:* \`${HOST}\`%0A🤖 *Estado:* Gateway iniciado y listo para recibir mensajes.%0A📅 *Fecha:* \`${DATE}\`"
MSG_WHATSAPP="🟢 *Hermes Gateway Online* 🟢\n\n🖥️ *Host:* ${HOST}\n🤖 *Estado:* Gateway iniciado y listo para recibir mensajes.\n📅 *Fecha:* ${DATE}"

# A) Send via Hermes Telegram Bot
if [[ -n "$TOKEN" && -n "$CHAT_ID" ]]; then
  curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -d "chat_id=${CHAT_ID}" \
    -d "text=${MSG_TELEGRAM}" \
    -d "parse_mode=Markdown" >/dev/null 2>&1 || true
fi

# B) Send via WhatsApp Baileys Bridge
if [[ -n "$WA_CHAT_ID" ]]; then
  # Wait for bridge port 3005 to respond
  for i in {1..10}; do
    if curl -s "http://127.0.0.1:${WA_PORT}/status" 2>/dev/null | grep -q "connected"; then
      break
    fi
    sleep 1
  done

  curl -s -X POST "http://127.0.0.1:${WA_PORT}/send" \
    -H "Content-Type: application/json" \
    -d "{\"chatId\":\"${WA_CHAT_ID}\",\"message\":\"${MSG_WHATSAPP}\"}" >/dev/null 2>&1 || true
fi

exit 0
