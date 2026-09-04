#!/usr/bin/env bash
# ==============================================================================
# Cron - VPS CPU, Steal & IOWait Health Monitor
# Checks 5-min load vs available cores and hypervisor steal time, sends alerts.
#
# - Saturación (load5 > cores x ratio): bot URGENTE (puede tumbar automatizaciones).
# - Solo steal alto: bot RUTINA (no accionable de noche; es evidencia para
#   reclamar al proveedor si es sostenido, típico en hosting oversold).
# - El log horario (cpu.log) sirve como historial/evidencia ante el proveedor.
# Reuses sentinel/.env for Telegram credentials — no secrets stored here.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 1. Optional local overrides (cron/.env is gitignored, see .env.example)
if [[ -f "${SCRIPT_DIR}/.env" ]]; then
  # shellcheck disable=SC1090
  source "${SCRIPT_DIR}/.env"
fi

# 2. Fallback: reuse Sentinel Telegram config for vars NOT explicitly set.
# Explicitly exported vars (even empty) win over the fallback file.
if [[ -f "${BASE_DIR}/sentinel/.env" ]]; then
  _saved_vars=""
  for _v in TELEGRAM_CHAT_ID TELEGRAM_BOT_URGENT_TOKEN TELEGRAM_BOT_ROUTINE_TOKEN TELEGRAM_BOT_TOKEN; do
    if [[ -n "${!_v+set}" ]]; then
      printf -v "_saved_${_v}" '%s' "${!_v}"
      _saved_vars="${_saved_vars} ${_v}"
    fi
  done
  # shellcheck disable=SC1090
  source "${BASE_DIR}/sentinel/.env"
  for _v in ${_saved_vars}; do
    _tmp="_saved_${_v}"
    printf -v "${_v}" '%s' "${!_tmp}"
  done
  unset _v _tmp _saved_vars _saved_TELEGRAM_CHAT_ID _saved_TELEGRAM_BOT_URGENT_TOKEN _saved_TELEGRAM_BOT_ROUTINE_TOKEN _saved_TELEGRAM_BOT_TOKEN
fi

LOAD_ALERT_RATIO="${LOAD_ALERT_RATIO:-1.0}"
STEAL_ALERT_THRESHOLD="${STEAL_ALERT_THRESHOLD:-10}"
NOTIFY_ON_HEALTHY="${NOTIFY_ON_HEALTHY:-false}"
ALERT_COOLDOWN_HOURS="${ALERT_COOLDOWN_HOURS:-6}"
URGENT_TOKEN="${TELEGRAM_BOT_URGENT_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"
ROUTINE_TOKEN="${TELEGRAM_BOT_ROUTINE_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"

send_telegram() {
  local token="$1" msg="$2"
  if [[ -n "${token}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
    curl -s -X POST "https://api.telegram.org/bot${token}/sendMessage" \
      -d "chat_id=${TELEGRAM_CHAT_ID}" \
      -d "text=${msg}" \
      -d "parse_mode=Markdown" >/dev/null 2>&1 || true
  fi
}

# Anti-spam: at most one alert per cooldown window (state file is gitignored)
COOLDOWN_FILE="${SCRIPT_DIR}/logs/.check_cpu.last_alert"
cooldown_active() {
  local last=0 now
  if [[ -f "${COOLDOWN_FILE}" ]]; then
    last="$(cat "${COOLDOWN_FILE}" 2>/dev/null || echo 0)"
    [[ "${last}" =~ ^[0-9]+$ ]] || last=0
  fi
  now="$(date +%s)"
  (( now - last < ALERT_COOLDOWN_HOURS * 3600 ))
}

CORES="$(nproc)"
read -r LOAD1 LOAD5 LOAD15 _ < /proc/loadavg

# Sample /proc/stat twice (5s apart) for steal/iowait/user/system breakdown
# NOTE: '|| true' because read exits 1 when input lacks trailing newline
read -r -a S1 < <(awk '/^cpu /{for(i=2;i<=NF;i++) printf "%s ", $i}' /proc/stat) || true
sleep 5
read -r -a S2 < <(awk '/^cpu /{for(i=2;i<=NF;i++) printf "%s ", $i}' /proc/stat) || true
# fields: user nice system idle iowait irq softirq steal guest guest_nice
T1=0; T2=0
for i in "${!S1[@]}"; do T1=$((T1 + S1[i])); T2=$((T2 + S2[i])); done
DT=$((T2 - T1)); [[ "${DT}" -le 0 ]] && DT=1
pct() { awk -v a="$1" -v b="$2" 'BEGIN{printf "%.1f", (b-a)*100/'"${DT}"'}'; }
STEAL_PCT="$(pct "${S1[7]:-0}" "${S2[7]:-0}")"
IOWAIT_PCT="$(pct "${S1[4]:-0}" "${S2[4]:-0}")"
USER_PCT="$(pct "${S1[0]:-0}" "${S2[0]:-0}")"
SYS_PCT="$(pct "${S1[2]:-0}" "${S2[2]:-0}")"

LOAD_LIMIT="$(awk -v c="${CORES}" -v r="${LOAD_ALERT_RATIO}" 'BEGIN{printf "%.2f", c*r}')"
LOAD_BREACH="$(awk -v l="${LOAD5}" -v lim="${LOAD_LIMIT}" 'BEGIN{print (l>=lim)}')"
STEAL_BREACH="$(awk -v s="${STEAL_PCT}" -v lim="${STEAL_ALERT_THRESHOLD}" 'BEGIN{print (s>=lim)}')"

echo "================================================================="
echo "🖥️  CPU Health Check: $(date -R)"
echo "⚙️  Cores: ${CORES} | Load5 límite: >= ${LOAD_LIMIT} | Steal límite: >= ${STEAL_ALERT_THRESHOLD}% (cooldown: ${ALERT_COOLDOWN_HOURS}h)"
echo "================================================================="
echo "[+] Load: ${LOAD1} (1m) / ${LOAD5} (5m) / ${LOAD15} (15m)"
echo "[+] CPU: user ${USER_PCT}% | sys ${SYS_PCT}% | iowait ${IOWAIT_PCT}% | steal ${STEAL_PCT}%"
echo "[+] Top CPU: $(ps -eo comm,pcpu --sort=-pcpu | grep -v '^ps ' | head -4 | tail -3 | awk '{printf "%s(%s%%) ", $1, $2}')"

if [[ "${LOAD_BREACH}" == "1" ]]; then
  echo "  [!] ⚠️ Saturación: load5 ${LOAD5} >= ${LOAD_LIMIT}. Enviando alerta URGENTE..."
  if cooldown_active; then
    echo "  [i] Cooldown activo. Omitiendo Telegram."
  else
    send_telegram "${URGENT_TOKEN}" "🚨 *ALERTA: CPU Saturada* 🚨%0A%0A🖥️ *Host:* \`$(hostname)\`%0A📊 *Load5:* \`${LOAD5}\` _(límite: ${LOAD_LIMIT} en ${CORES} cores)_%0A📈 *Load:* 1m=\`${LOAD1}\` 15m=\`${LOAD15}\`%0A⚙️ *CPU:* user ${USER_PCT}% sys ${SYS_PCT}% iowait ${IOWAIT_PCT}% steal ${STEAL_PCT}%25%0A%0A💡 *Acciones sugeridas:*%0A• \`htop\` / \`docker stats\` para hallar el culpable%0A• Escalonar automatizaciones Steel"
    date +%s > "${COOLDOWN_FILE}"
  fi
elif [[ "${STEAL_BREACH}" == "1" ]]; then
  echo "  [!] ⚠️ Steal alto: ${STEAL_PCT}% >= ${STEAL_ALERT_THRESHOLD}%. Enviando aviso RUTINA..."
  if cooldown_active; then
    echo "  [i] Cooldown activo. Omitiendo Telegram."
  else
    send_telegram "${ROUTINE_TOKEN}" "⚠️ *Aviso: CPU Steal Alto* ⚠️%0A%0A🖥️ *Host:* \`$(hostname)\`%0A🥷 *Steal:* \`${STEAL_PCT}%\` _(límite: ${STEAL_ALERT_THRESHOLD}%)_%0A📊 *Load:* 1m=\`${LOAD1}\` 5m=\`${LOAD5}\`%0A%0A💡 El hipervisor te está quitando CPU (overselling). Si se repite varios días, reclamar al proveedor con \`cron/logs/cpu.log\` como evidencia."
    date +%s > "${COOLDOWN_FILE}"
  fi
else
  echo "[+] ✓ CPU saludable (load5 ${LOAD5} < ${LOAD_LIMIT}, steal ${STEAL_PCT}% < ${STEAL_ALERT_THRESHOLD}%)."
  if [[ "${NOTIFY_ON_HEALTHY}" == "true" ]]; then
    send_telegram "${ROUTINE_TOKEN}" "✅ *CPU Saludable* ✅%0A%0A🖥️ *Host:* \`$(hostname)\`%0A📊 Load5: \`${LOAD5}\` | Steal: \`${STEAL_PCT}%\`"
  fi
fi

echo "================================================================="
