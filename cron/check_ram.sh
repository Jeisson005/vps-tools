#!/usr/bin/env bash
# ==============================================================================
# Cron - VPS RAM & Swap Health Monitor
# Checks memory usage against configurable thresholds and sends Telegram alerts.
# Companion to sentinel/scripts/check_disk.sh (disk) but lives in cron/ and
# reuses the Sentinel .env for Telegram credentials (no secrets stored here).
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 1. Optional local overrides (cron/.env is gitignored, see .env.example)
if [[ -f "${SCRIPT_DIR}/.env" ]]; then
  # shellcheck disable=SC1090
  source "${SCRIPT_DIR}/.env"
fi

# 2. Fallback: reuse Sentinel Telegram config so no token is duplicated here
if [[ -z "${TELEGRAM_CHAT_ID:-}" && -f "${BASE_DIR}/sentinel/.env" ]]; then
  # shellcheck disable=SC1090
  source "${BASE_DIR}/sentinel/.env"
fi

RAM_ALERT_THRESHOLD="${RAM_ALERT_THRESHOLD:-85}"
SWAP_ALERT_THRESHOLD="${SWAP_ALERT_THRESHOLD:-70}"
NOTIFY_ON_HEALTHY="${NOTIFY_ON_HEALTHY:-false}"
TELEGRAM_TOKEN="${TELEGRAM_BOT_URGENT_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"

send_telegram() {
  local msg="$1"
  if [[ -n "${TELEGRAM_TOKEN}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
      -d "chat_id=${TELEGRAM_CHAT_ID}" \
      -d "text=${msg}" \
      -d "parse_mode=Markdown" >/dev/null 2>&1 || true
  fi
}

echo "================================================================="
echo "🧠 RAM Health Check: $(date -R)"
echo "⚙️  Thresholds: RAM >= ${RAM_ALERT_THRESHOLD}% | Swap >= ${SWAP_ALERT_THRESHOLD}%"
echo "================================================================="

# --- RAM ---
read -r MEM_TOTAL MEM_USED MEM_FREE MEM_SHARED MEM_CACHE MEM_AVAIL <<< \
  "$(free -m | awk '/^Mem:/ {print $2, $3, $4, $5, $6, $7}')"
RAM_PCT=$((MEM_TOTAL > 0 ? (MEM_USED * 100) / MEM_TOTAL : 0))

# --- Swap ---
read -r SWAP_TOTAL SWAP_USED SWAP_FREE <<< \
  "$(free -m | awk '/^Swap:/ {print $2, $3, $4}')"
if [[ "${SWAP_TOTAL}" -gt 0 ]]; then
  SWAP_PCT=$(( (SWAP_USED * 100) / SWAP_TOTAL ))
else
  SWAP_PCT=0
fi

# --- Top consumers (for the alert context) ---
TOP_PROCS="$(ps -eo comm,rss --sort=-rss | head -6 | tail -5 | awk '{printf "• %s (%d MB)\\n", $1, $2/1024}')"

echo "[+] RAM:  ${RAM_PCT}% usado (${MEM_USED}/${MEM_TOTAL} MB, disponible: ${MEM_AVAIL} MB)"
echo "[+] Swap: ${SWAP_PCT}% usado (${SWAP_USED}/${SWAP_TOTAL} MB)"

ALERT_TRIGGERED=false
ALERT_REASON=""

if [[ "${RAM_PCT}" -ge "${RAM_ALERT_THRESHOLD}" ]]; then
  ALERT_TRIGGERED=true
  ALERT_REASON="RAM en ${RAM_PCT}% (límite ${RAM_ALERT_THRESHOLD}%)"
  echo "  [!] ⚠️ RAM alta. Enviando alerta..."
fi

if [[ "${SWAP_TOTAL}" -gt 0 && "${SWAP_PCT}" -ge "${SWAP_ALERT_THRESHOLD}" ]]; then
  ALERT_TRIGGERED=true
  if [[ -n "${ALERT_REASON}" ]]; then
    ALERT_REASON="${ALERT_REASON} + Swap en ${SWAP_PCT}% (límite ${SWAP_ALERT_THRESHOLD}%)"
  else
    ALERT_REASON="Swap en ${SWAP_PCT}% (límite ${SWAP_ALERT_THRESHOLD}%)"
  fi
  echo "  [!] ⚠️ Swap alto. Enviando alerta..."
fi

if [[ "${ALERT_TRIGGERED}" == "true" ]]; then
  MSG="🚨 *ALERTA: Memoria Alta* 🚨%0A%0A🖥️ *Host:* \`$(hostname)\`%0A📊 *Causa:* ${ALERT_REASON}%0A🧠 *RAM:* \`${RAM_PCT}% usado\` (${MEM_USED}/${MEM_TOTAL} MB, disp: ${MEM_AVAIL} MB)%0A💾 *Swap:* \`${SWAP_PCT}% usado\` (${SWAP_USED}/${SWAP_TOTAL} MB)%0A%0A🔝 *Top procesos:*%0A${TOP_PROCS}%0A%0A💡 *Acciones sugeridas:*%0A• \`cron/nightly_refresh.sh\` (reinicio nocturno)%0A• \`docker stats --no-stream\`%0A• Revisar Steel/Chromium si hay automatizaciones colgadas"
  send_telegram "${MSG}"
else
  echo "[+] ✓ Memoria saludable (RAM ${RAM_PCT}% < ${RAM_ALERT_THRESHOLD}%, Swap ${SWAP_PCT}% < ${SWAP_ALERT_THRESHOLD}%)."
  if [[ "${NOTIFY_ON_HEALTHY}" == "true" ]]; then
    send_telegram "✅ *RAM Saludable* ✅%0A%0A🖥️ *Host:* \`$(hostname)\`%0A🧠 RAM: \`${RAM_PCT}%\` | Swap: \`${SWAP_PCT}%\`"
  fi
fi

echo "================================================================="
