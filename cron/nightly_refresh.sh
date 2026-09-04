#!/usr/bin/env bash
# ==============================================================================
# Cron - Nightly Refresh (madrugada)
# Reinicia servicios web con fugas de memoria conocidas y hace limpieza ligera.
#
# SEGURO de reiniciar (stateless, sin automatizaciones):
#   - opencode-web (systemd): leak conocido, VSZ crece sin control
#   - open-webui (docker): worker python ~700MB, UI de chat sin estado crítico
#   - rustdesk-web (docker): suele quedar 'unhealthy' + CPU alto en loop
#
# NUNCA toca (pueden tener automatizaciones o mensajes en vuelo):
#   - steel-browser* , wa-* , hermes-* , sentinel , nginx , headscale
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
REFRESH_OPEN_WEBUI="${REFRESH_OPEN_WEBUI:-true}"
REFRESH_RUSTDESK_WEB="${REFRESH_RUSTDESK_WEB:-true}"
DOCKER_BUILDER_PRUNE="${DOCKER_BUILDER_PRUNE:-true}"
CLEAN_TMP="${CLEAN_TMP:-true}"
JOURNAL_VACUUM_SIZE="${JOURNAL_VACUUM_SIZE:-500M}"

# Telegram opcional (reutiliza sentinel/.env, igual que check_ram.sh)
if [[ -z "${TELEGRAM_CHAT_ID:-}" && -f "${BASE_DIR}/sentinel/.env" ]]; then
  # shellcheck disable=SC1090
  source "${BASE_DIR}/sentinel/.env"
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

# --- 2. open-webui (docker) ---
if [[ "${REFRESH_OPEN_WEBUI}" == "true" ]]; then
  log "--- open-webui ---"
  if docker restart open-webui >/dev/null 2>&1; then
    sleep 15
    if [[ "$(docker inspect open-webui --format '{{.State.Status}}' 2>/dev/null)" == "running" ]]; then
      log "[+] open-webui reiniciado y running"
    else
      log "[!] open-webui NO quedó running tras reinicio"
      FAILED="${FAILED} open-webui"
    fi
  else
    log "[!] no se pudo reiniciar open-webui (¿contenedor inexistente?)"
    FAILED="${FAILED} open-webui(restart)"
  fi
else
  log "--- open-webui omitido (REFRESH_OPEN_WEBUI=false) ---"
fi

# --- 3. rustdesk-web (docker, suele quedar unhealthy) ---
if [[ "${REFRESH_RUSTDESK_WEB}" == "true" ]]; then
  log "--- rustdesk-web ---"
  if docker restart rustdesk-web >/dev/null 2>&1; then
    log "[+] rustdesk-web reiniciado"
  else
    log "[!] no se pudo reiniciar rustdesk-web"
    FAILED="${FAILED} rustdesk-web"
  fi
else
  log "--- rustdesk-web omitido (REFRESH_RUSTDESK_WEB=false) ---"
fi

# --- 4. Limpieza ligera docker (solo caché huérfana, nada tagged) ---
if [[ "${DOCKER_BUILDER_PRUNE}" == "true" ]]; then
  log "--- docker builder prune ---"
  docker builder prune -f >/dev/null 2>&1 || log "[!] builder prune falló"
  docker image prune -f >/dev/null 2>&1 || log "[!] image prune falló"
  log "[+] prune de caché huérfana OK"
fi

# --- 5. Limpieza /tmp (restos de backups de prueba y sesiones chrome viejas) ---
if [[ "${CLEAN_TMP}" == "true" ]]; then
  log "--- /tmp cleanup ---"
  rm -rf /tmp/vps-backups /tmp/test_backup_vps 2>/dev/null || true
  find /tmp -maxdepth 1 -name 'chrome-*' -mtime +7 -exec rm -rf {} + 2>/dev/null || true
  log "[+] /tmp liviano OK"
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
