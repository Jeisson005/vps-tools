#!/usr/bin/env bash
# ==============================================================================
# Sentinel - VPS Disk Space Health Monitor
# Checks disk usage against configurable thresholds and sends Telegram alerts.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${BASE_DIR}/.env"

# Load configuration if present
if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
fi

DISK_ALERT_THRESHOLD="${DISK_ALERT_THRESHOLD:-85}"
MONITORED_MOUNTS="${MONITORED_MOUNTS:-/}"
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
echo "🛡️  Sentinel Disk Space Check: $(date -R)"
echo "⚙️  Threshold: >= ${DISK_ALERT_THRESHOLD}%"
echo "📂 Mounts: ${MONITORED_MOUNTS}"
echo "================================================================="

ALERT_TRIGGERED=false

for mount in ${MONITORED_MOUNTS}; do
  if ! df -P "${mount}" &>/dev/null; then
    echo "[-] WARNING: Mount point '${mount}' not found. Skipping." >&2
    continue
  fi

  # Extract usage percentage, total, used, and available space
  DF_OUTPUT=$(df -Ph "${mount}" | tail -n 1)
  TOTAL=$(echo "${DF_OUTPUT}" | awk '{print $2}')
  USED=$(echo "${DF_OUTPUT}" | awk '{print $3}')
  AVAIL=$(echo "${DF_OUTPUT}" | awk '{print $4}')
  USAGE_PCT=$(echo "${DF_OUTPUT}" | awk '{print $5}' | tr -d '%')

  echo "[+] Mount: '${mount}' | Used: ${USAGE_PCT}% (${USED}/${TOTAL}, Avail: ${AVAIL})"

  if [[ "${USAGE_PCT}" -ge "${DISK_ALERT_THRESHOLD}" ]]; then
    ALERT_TRIGGERED=true
    echo "  [!] ⚠️ Disk usage on '${mount}' is ${USAGE_PCT}% (>= ${DISK_ALERT_THRESHOLD}%). Sending alert..."

    MSG="🚨 *ALERTA: Espacio en Disco Crítico* 🚨%0A%0A🖥️ *Host:* \`$(hostname)\`%0A💽 *Montaje:* \`${mount}\`%0A📊 *Uso actual:* \`${USAGE_PCT}%\` _(Límite: ${DISK_ALERT_THRESHOLD}%)_%0A💾 *Libre:* \`${AVAIL}\` de \`${TOTAL}\`%0A%0A💡 *Sugerencias de limpieza:*%0A• \`docker system prune -f\`%0A• \`journalctl --vacuum-size=500M\`%0A• \`~/vps-tools/cron/cleanup_logs.sh\`"
    send_telegram "${MSG}"
  fi
done

if [[ "${ALERT_TRIGGERED}" == "false" ]]; then
  echo "[+] ✓ All monitored mounts are healthy (under ${DISK_ALERT_THRESHOLD}%)."
  if [[ "${NOTIFY_ON_HEALTHY}" == "true" ]]; then
    send_telegram "✅ *Sentinel - Disco Saludable* ✅%0A%0A🖥️ *Host:* \`$(hostname)\`%0A💽 Todos los puntos de montaje están por debajo del ${DISK_ALERT_THRESHOLD}% de uso."
  fi
fi

echo "================================================================="
