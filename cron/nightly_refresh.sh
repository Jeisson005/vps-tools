#!/usr/bin/env bash
# ==============================================================================
# Cron - Nightly Refresh (madrugada)
# Reinicia servicios web con fugas de memoria conocidas y hace limpieza ligera.
#
# SEGURO de reiniciar (stateless, sin automatizaciones):
#   - opencode-web (systemd): leak conocido, VSZ crece sin control
#
# NUNCA toca (pueden tener automatizaciones o mensajes en vuelo):
#   - steel-browser* , sentinel , nginx , headscale
#     (las sesiones Steel >24h SÍ se liberan vía API; al terminar, los workers
#      que quedan SIN sesiones se reciclan con restart para limpiar SingletonLock
#      y zombies. Desactivable con CLEAN_STEEL_SESSIONS=false en cron/.env)
#
# REFRESCADOS con health-check (opt-out vía cron/.env):
#   - wa-* (MCP WhatsApp personal): 'docker restart' + GET /status
#   Se reinicia porque Baileys acumula sesiones E2EE y reconexiones 408/428;
#   el health-check evita dar por bueno un reinicio fallido. Si prefieres
#   no tocarlo, pon REFRESH_WHATSAPP_MCP=false.
#
# Hermes NO se toca aquí (ver cron/monthly_hermes_refresh.sh, día 15 02:45).
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

REFRESH_OPENCODE="${REFRESH_OPENCODE:-true}"
REFRESH_WHATSAPP_MCP="${REFRESH_WHATSAPP_MCP:-true}"
WHATSAPP_MCP_PORT="${WHATSAPP_MCP_PORT:-3159}"
DOCKER_BUILDER_PRUNE="${DOCKER_BUILDER_PRUNE:-true}"
CLEAN_TMP="${CLEAN_TMP:-true}"
JOURNAL_VACUUM_SIZE="${JOURNAL_VACUUM_SIZE:-500M}"
CLEAN_STEEL_SESSIONS="${CLEAN_STEEL_SESSIONS:-true}"

# Telegram opcional: reutiliza sentinel/.env solo para vars NO fijadas
# explícitamente (igual que check_ram.sh / check_disk.sh).
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
NOTIFY_ON_REFRESH="${NOTIFY_ON_REFRESH:-false}"

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
log "🌙 Nightly refresh iniciado"
log "RAM antes: $(free -m | awk '/^Mem:/ {printf "%d/%d MB (%d%%)", $3, $2, $3*100/$2}') | Swap: $(free -m | awk '/^Swap:/ {printf "%d/%d MB", $3, $2}')"

# --- 1. opencode-web (systemd) ---
if [[ "${REFRESH_OPENCODE}" == "true" ]]; then
  log "--- opencode-web ---"
  if sudo -n systemctl restart opencode-web 2>&1; then
    sleep 8
    if systemctl is-active --quiet opencode-web; then
      log "[+] opencode-web reiniciado y activo"
    else
      log "[!] opencode-web NO quedó activo tras reinicio"
      FAILED="${FAILED} opencode-web"
    fi
  else
    log "[!] sin permiso sudo para systemctl, se omite opencode-web"
    FAILED="${FAILED} opencode-web(sudo)"
  fi
else
  log "--- opencode-web omitido (REFRESH_OPENCODE=false) ---"
fi

# --- 2. wa-jeisson (MCP WhatsApp personal, docker) ---
if [[ "${REFRESH_WHATSAPP_MCP}" == "true" ]]; then
  log "--- wa-jeisson (MCP WhatsApp :${WHATSAPP_MCP_PORT}) ---"
  if docker inspect wa-jeisson >/dev/null 2>&1; then
    if docker restart wa-jeisson >/dev/null 2>&1; then
      # Baileys tarda ~5-15s en reconectar y re-hacer history sync
      for _i in $(seq 1 12); do
        _st="$(curl -s --max-time 3 "http://127.0.0.1:${WHATSAPP_MCP_PORT}/status" 2>/dev/null || true)"
        if echo "${_st}" | grep -q '"connected":true'; then
          log "[+] wa-jeisson reiniciado y connected"
          break
        fi
        sleep 5
        if [[ "${_i}" == "12" ]]; then
          log "[!] wa-jeisson reiniciado pero sin /status connected: ${_st:0:120}"
          FAILED="${FAILED} wa-jeisson(health)"
        fi
      done
    else
      log "[!] no se pudo reiniciar wa-jeisson"
      FAILED="${FAILED} wa-jeisson(restart)"
    fi
  else
    log "[!] contenedor wa-jeisson inexistente, se omite (¿cuenta eliminada?)"
    FAILED="${FAILED} wa-jeisson(missing)"
  fi
else
  log "--- wa-jeisson omitido (REFRESH_WHATSAPP_MCP=false) ---"
fi

# --- 3. Limpieza ligera docker (solo caché huérfana, nada tagged) ---
if [[ "${DOCKER_BUILDER_PRUNE}" == "true" ]]; then
  log "--- docker builder prune ---"
  docker builder prune -f >/dev/null 2>&1 || log "[!] builder prune falló"
  docker image prune -f >/dev/null 2>&1 || log "[!] image prune falló"
  log "[+] prune de caché huérfana OK"
fi

# --- 4. Limpieza /tmp (restos de backups de prueba y sesiones chrome viejas) ---
if [[ "${CLEAN_TMP}" == "true" ]]; then
  log "--- /tmp cleanup ---"
  rm -rf /tmp/vps-backups /tmp/test_backup_vps 2>/dev/null || true
  find /tmp -maxdepth 1 -name 'chrome-*' -mtime +7 -exec rm -rf {} + 2>/dev/null || true
  log "[+] /tmp liviano OK"
fi

# --- 5. Steel sessions: liberar >24h vía API (NO reinicia contenedores) ---
if [[ "${CLEAN_STEEL_SESSIONS}" == "true" ]]; then
  log "--- steel session cleanup ---"
  _steel_cleanup="${BASE_DIR}/steel/scripts/cleanup_sessions.sh"
  if [[ -x "${_steel_cleanup}" ]]; then
    _out="$("${_steel_cleanup}" 2>&1)"
    log "$(printf '%s' "${_out}" | tail -n 1)"
  else
    log "[!] no se encontró ${_steel_cleanup}"
  fi
fi

# --- 6. Journal vacuum (evita que /var/log crezca sin control) ---
if [[ -n "${JOURNAL_VACUUM_SIZE}" && "${JOURNAL_VACUUM_SIZE}" != "0" ]]; then
  log "--- journal vacuum (${JOURNAL_VACUUM_SIZE}) ---"
  sudo -n journalctl --vacuum-size="${JOURNAL_VACUUM_SIZE}" 2>&1 | tail -1 || log "[!] journal vacuum falló"
fi

log "RAM después: $(free -m | awk '/^Mem:/ {printf "%d/%d MB (%d%%)", $3, $2, $3*100/$2}') | Swap: $(free -m | awk '/^Swap:/ {printf "%d/%d MB", $3, $2}')"

if [[ -z "${FAILED}" ]]; then
  log "[+] ✓ Nightly refresh completado sin errores"
  [[ "${NOTIFY_ON_REFRESH}" == "true" ]] && send_telegram "🌙 *Nightly refresh OK*%0A🖥️ \`$(hostname)\`%0A🧠 RAM: \`$(free -m | awk '/^Mem:/ {printf "%d%%", $3*100/$2}')\`"
else
  log "[!] ⚠️ Fallos:${FAILED}"
  send_telegram "⚠️ *Nightly refresh con fallos* ⚠️%0A🖥️ \`$(hostname)\`%0A❌ Fallos:\`${FAILED}\`"
fi
log "================================================================="
