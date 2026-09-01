#!/usr/bin/env bash
# ==============================================================================
# Headscale Linux Client Management CLI
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load .env if present
if [[ -f "${CLIENT_DIR}/.env" ]]; then
  # shellcheck disable=SC1091
  source "${CLIENT_DIR}/.env"
elif [[ -f "${CLIENT_DIR}/.env.example" ]]; then
  # shellcheck disable=SC1091
  source "${CLIENT_DIR}/.env.example"
fi

HEADSCALE_URL="${HEADSCALE_URL:-https://headscale.jeisson.top}"
HEADSCALE_AUTH_KEY="${HEADSCALE_AUTH_KEY:-ccf3d9a6b227d5f4ae3a9dfdc0eab8ad701096ba21e8117b}"
CLIENT_HOSTNAME="${CLIENT_HOSTNAME:-$(hostname)}"
EXIT_NODE="${EXIT_NODE:-100.64.0.4}"

# Formatting colors
CLR_GREEN="\e[32m"
CLR_RED="\e[31m"
CLR_YELLOW="\e[33m"
CLR_BLUE="\e[34m"
CLR_CYAN="\e[36m"
CLR_BOLD="\e[1m"
CLR_RESET="\e[0m"

log_info() { echo -e "${CLR_BLUE}[INFO]${CLR_RESET} $*"; }
log_ok()   { echo -e "${CLR_GREEN}[OK]${CLR_RESET} $*"; }
log_warn() { echo -e "${CLR_YELLOW}[WARN]${CLR_RESET} $*"; }
log_err()  { echo -e "${CLR_RED}[ERR]${CLR_RESET} $*" >&2; }

require_tailscale() {
  if ! command -v tailscale >/dev/null 2>&1; then
    log_err "Tailscale CLI ('tailscale') is not installed on this system."
    log_info "Install it with: curl -fsSL https://tailscale.com/install.sh | sh"
    exit 1
  fi
}

cmd_status() {
  require_tailscale
  echo -e "${CLR_BOLD}=== ESTADO DE LA CONEXIÓN HEADSCALE VPN ===${CLR_RESET}"
  
  local TS_STATUS
  TS_STATUS=$(tailscale status 2>/dev/null || echo "stopped")
  
  if echo "${TS_STATUS}" | grep -qi "logged out\|stopped\|Tailscale is stopped"; then
    echo -e "Estado VPN:     ${CLR_RED}🔴 Desconectado${CLR_RESET}"
    return 0
  fi

  local IP_V4
  IP_V4=$(tailscale ip -4 2>/dev/null || echo "Desconocida")
  local IP_V6
  IP_V6=$(tailscale ip -6 2>/dev/null || echo "Desconocida")
  
  # Check exit node
  local EXIT_STATUS
  local CURRENT_EXIT
  CURRENT_EXIT=$(tailscale status --json 2>/dev/null | grep -o '"ExitNodeIP": *"[^"]*"' | head -n 1 | cut -d'"' -f4 || true)
  
  if [[ -n "${CURRENT_EXIT}" && "${CURRENT_EXIT}" != "null" ]]; then
    EXIT_STATUS="${CLR_GREEN}🟢 ACTIVO (Todo el tráfico pasa por VPS: ${CURRENT_EXIT})${CLR_RESET}"
  else
    EXIT_STATUS="${CLR_CYAN}⚪ DIRECTO / MESH (Solo tráfico VPN pasa por VPS)${CLR_RESET}"
  fi

  # Public IP check
  local PUB_IP
  PUB_IP=$(curl -s --max-time 3 https://api.ipify.org 2>/dev/null || echo "N/A")

  echo -e "Estado VPN:     ${CLR_GREEN}🟢 Conectado${CLR_RESET}"
  echo -e "IP VPN Local:   ${CLR_CYAN}${IP_V4}${CLR_RESET} (${IP_V6})"
  echo -e "Modo de Salida: ${EXIT_STATUS}"
  echo -e "IP Pública Ext: ${CLR_BOLD}${PUB_IP}${CLR_RESET}"
  echo -e "Servidor Control: ${HEADSCALE_URL}"
  echo ""
  echo -e "${CLR_BOLD}Dispositivos en la Malla (Peers):${CLR_RESET}"
  tailscale status
}

cmd_up() {
  require_tailscale
  log_info "Conectando cliente a Headscale (${HEADSCALE_URL})..."
  
  local AUTH_FLAG=""
  if [[ -n "${HEADSCALE_AUTH_KEY}" ]]; then
    AUTH_FLAG="--authkey=${HEADSCALE_AUTH_KEY}"
  fi

  sudo tailscale up \
    --login-server="${HEADSCALE_URL}" \
    ${AUTH_FLAG} \
    --hostname="${CLIENT_HOSTNAME}" \
    --accept-routes \
    --reset

  log_ok "Conexión establecida exitosamente."
  cmd_status
}

cmd_down() {
  require_tailscale
  log_info "Desconectando Tailscale VPN..."
  sudo tailscale down
  log_ok "VPN desconectada."
}

cmd_mode() {
  require_tailscale
  local TARGET_MODE="${1:-}"

  case "${TARGET_MODE}" in
    full|exit|vps)
      log_info "Activando MODO FULL (Exit Node en ${EXIT_NODE})..."
      sudo tailscale set --exit-node="${EXIT_NODE}" --exit-node-allow-lan-access=true
      log_ok "Modo Full activado: Todo tu tráfico de internet ahora navega a través del VPS."
      ;;
    direct|mesh|server-only|none)
      log_info "Desactivando Exit Node (Cambiando a Modo Mesh Directo)..."
      sudo tailscale set --exit-node=""
      log_ok "Modo Directo activado: Tu tráfico general sale por tu ISP local; solo la VPN va al VPS."
      ;;
    *)
      log_err "Modo desconocido '${TARGET_MODE}'. Opciones: 'full' o 'direct'"
      exit 1
      ;;
  esac
}

cmd_toggle() {
  require_tailscale
  local CURRENT_EXIT
  CURRENT_EXIT=$(tailscale status --json 2>/dev/null | grep -o '"ExitNodeIP": *"[^"]*"' | head -n 1 | cut -d'"' -f4 || true)

  if [[ -n "${CURRENT_EXIT}" && "${CURRENT_EXIT}" != "null" ]]; then
    cmd_mode direct
  else
    cmd_mode full
  fi
}

cmd_ping() {
  require_tailscale
  log_info "Probando conectividad contra el nodo VPS (${EXIT_NODE})..."
  ping -c 4 "${EXIT_NODE}" || true
}

show_help() {
  echo -e "${CLR_BOLD}Headscale Linux Client Manager${CLR_RESET}"
  echo "Uso: $0 [comando]"
  echo ""
  echo "Comandos disponibles:"
  echo "  up | connect        Conectar Tailscale al servidor Headscale"
  echo "  down | disconnect   Desconectar VPN"
  echo "  status              Ver estado de la VPN, IPs, Exit Node y Peers"
  echo "  mode full           Redirigir TODO el tráfico de internet a través del VPS"
  echo "  mode direct         Modo Mesh (solo tráfico de VPN por VPS, internet directo)"
  echo "  switch | toggle     Alternar entre Modo Full y Modo Directo"
  echo "  ping                Probar latencia contra el servidor VPS (${EXIT_NODE})"
  echo "  help                Mostrar esta ayuda"
}

# Main dispatcher
ACTION="${1:-status}"
shift || true

case "${ACTION}" in
  up|connect|start)
    cmd_up "$@"
    ;;
  down|disconnect|stop)
    cmd_down
    ;;
  status|info)
    cmd_status
    ;;
  mode)
    cmd_mode "${1:-full}"
    ;;
  switch|toggle)
    cmd_toggle
    ;;
  ping|test)
    cmd_ping
    ;;
  help|--help|-h)
    show_help
    ;;
  *)
    log_err "Acción desconocida '${ACTION}'"
    show_help
    exit 1
    ;;
esac
