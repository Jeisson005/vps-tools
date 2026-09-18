#!/usr/bin/env bash
# ==============================================================================
# Cron - Monthly Hermes Gateway Refresh (día 15, 02:45 AM)
# Reinicio mensual preventivo del agente Hermes (hermes-gateway.service):
# el puente Baileys acumula sesiones E2EE y reconexiones 408/428 con el tiempo.
#
# - Se ejecuta el día 15 a las 02:45 para NO colisionar con:
#     · nightly_refresh.sh (diario 02:30, termina ~02:32)
#     · backup a Drive (diario 03:30)
#     · auditoría de seguridad mensual (día 1, 03:00)
# - Guarda anti-trabajo-en-curso: si hay sesiones de chat activas
#   (~/.hermes/runtime/active_sessions.json con entradas), se omite el
#   reinicio y se reintenta el próximo mes. Nunca mata una conversación activa.
# - Solo notifica por Telegram si algo FALLA (mismo patrón que nightly_refresh).
#   El arranque siempre avisa con el "🟢 online" de notify_ready.sh (como antes).
#
# Todo es configurable vía cron/.env (ver .env.example). Sin secretos aquí.
# ==============================================================================

set -u
# Nota: sin 'set -e' a propósito: un fallo no debe abortar el resto.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${SCRIPT_DIR}/.env" ]]; then
  # shellcheck disable=SC1090
  source "${SCRIPT_DIR}/.env"
fi

HERMES_BRIDGE_PORT="${HERMES_BRIDGE_PORT:-3005}"

# Telegram opcional: reutiliza sentinel/.env (igual que nightly_refresh.sh).
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
TELEGRAM_TOKEN="${TELEGRAM_BOT_ROUTINE_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"

send_telegram() {
  local msg="$1"
  if [[ -n "${TELEGRAM_TOKEN}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
      -d "chat_id=${TELEGRAM_CHAT_ID}" \
      -d "text=${msg}" \
      -d "parse_mode=Markdown" >/dev/null 2>&1 || true
  fi
}

log() { echo "[$(date '+%F %T')] $*"; }
FAILED=""

log "================================================================="
log "🌙 Monthly Hermes refresh iniciado"

# --- 1. Guarda: no reiniciar con sesiones de chat activas ---
_active="0"
_sessions_file="${HOME:-/home/jeisson}/.hermes/runtime/active_sessions.json"
if [[ -f "${_sessions_file}" ]]; then
  _active="$(python3 -c "import json,sys; print(len(json.load(open(sys.argv[1])).get('entries', [])))" "${_sessions_file}" 2>/dev/null || echo "0")"
fi
if [[ "${_active}" != "0" ]]; then
  log "[i] ${_active} sesión(es) activa(s), se omite el reinicio (reintento el próximo mes)"
  log "================================================================="
  exit 0
fi

# --- 2. Restart + health-check ---
log "--- hermes-gateway (agente + puente WhatsApp :${HERMES_BRIDGE_PORT}) ---"
if sudo -n systemctl restart hermes-gateway.service 2>&1; then
  # El agente tarda ~15-30s en levantar gateway + bridge.js
  sleep 20
  if systemctl is-active --quiet hermes-gateway.service; then
    _hh="$(curl -s --max-time 3 "http://127.0.0.1:${HERMES_BRIDGE_PORT}/health" 2>/dev/null || true)"
    if echo "${_hh}" | grep -q '"status":"connected"'; then
      log "[+] hermes-gateway reiniciado y puente connected"
    else
      log "[!] hermes-gateway activo pero puente sin connected: ${_hh:0:120}"
      FAILED="${FAILED} hermes-gateway(bridge)"
    fi
  else
    log "[!] hermes-gateway NO quedó activo tras reinicio"
    FAILED="${FAILED} hermes-gateway"
  fi
else
  log "[!] sin permiso sudo para systemctl, se omite hermes-gateway"
  FAILED="${FAILED} hermes-gateway(sudo)"
fi

if [[ -z "${FAILED}" ]]; then
  log "[+] ✓ Monthly Hermes refresh completado sin errores"
else
  log "[!] ⚠️ Fallos:${FAILED}"
  send_telegram "⚠️ *Monthly Hermes refresh con fallos* ⚠️%0A🖥️ \`$(hostname)\`%0A❌ Fallos:\`${FAILED}\`"
fi
log "================================================================="
