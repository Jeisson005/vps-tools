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
  
  local TS_JSON
  TS_JSON=$(tailscale status --json 2>/dev/null || echo "{}")
  local BACKEND_STATE
  BACKEND_STATE=$(echo "${TS_JSON}" | grep -o '"BackendState": *"[^"]*"' | head -n 1 | cut -d'"' -f4 || echo "Stopped")
  
  if [[ "${BACKEND_STATE}" != "Running" ]]; then
    echo -e "Estado VPN:         ${CLR_RED}🔴 Desconectado (${BACKEND_STATE})${CLR_RESET}"
  else
    local IP_V4
    IP_V4=$(tailscale ip -4 2>/dev/null || echo "-")
    local IP_V6
    IP_V6=$(tailscale ip -6 2>/dev/null || echo "-")
    
    local CURRENT_EXIT
    CURRENT_EXIT=$(tailscale status 2>/dev/null | grep "active; exit node" | awk '{print $1}' || true)
    
    local EXIT_STATUS
    if [[ -n "${CURRENT_EXIT}" ]]; then
      EXIT_STATUS="${CLR_GREEN}🟢 TÚNEL COMPLETO (Exit Node: ${CURRENT_EXIT})${CLR_RESET}"
    else
      EXIT_STATUS="${CLR_CYAN}⚪ MODO MALLA (Mesh - Tráfico general por ISP)${CLR_RESET}"
    fi

    local PUB_IP
    PUB_IP=$(curl -s --max-time 3 https://api.ipify.org 2>/dev/null || echo "N/A")

    echo -e "Estado VPN:         ${CLR_GREEN}🟢 Conectado${CLR_RESET}"
    echo -e "IP VPN Local:       ${CLR_CYAN}${IP_V4}${CLR_RESET} (${IP_V6})"
    echo -e "Modo Enrutamiento:  ${EXIT_STATUS}"
    echo -e "IP Pública Salida:  ${CLR_BOLD}${PUB_IP}${CLR_RESET}"
  fi

  # Autostart status
  local AUTO_ST
  if command -v systemctl >/dev/null 2>&1; then
    if sudo systemctl is-enabled tailscaled >/dev/null 2>&1; then
      AUTO_ST="${CLR_GREEN}Habilitado (Inicia con el sistema)${CLR_RESET}"
    else
      AUTO_ST="${CLR_YELLOW}Deshabilitado (Manual)${CLR_RESET}"
    fi
  else
    AUTO_ST="N/A"
  fi
  echo -e "Inicio Automático:  ${AUTO_ST}"

  # Proxy status
  local PROXY_ST
  if ss -tulpn 2>/dev/null | grep -q "127.0.0.1:1080"; then
    PROXY_ST="${CLR_GREEN}🟢 Activo (SOCKS5: 127.0.0.1:1080 | HTTP: 127.0.0.1:8080)${CLR_RESET}"
  else
    PROXY_ST="${CLR_YELLOW}⚪ Inactivo${CLR_RESET}"
  fi
  echo -e "Proxy Nativo:       ${PROXY_ST}"
  echo -e "Servidor Control:   ${HEADSCALE_URL}"
  
  if [[ "${BACKEND_STATE}" == "Running" ]]; then
    echo ""
    echo -e "${CLR_BOLD}Dispositivos en la Malla (Peers):${CLR_RESET}"
    tailscale status
  fi
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
    full|exit|exit-node|tunel)
      local SELECTED_NODE="${2:-${EXIT_NODE}}"
      log_info "Activando TÚNEL COMPLETO (Exit Node: ${SELECTED_NODE})..."
      sudo tailscale set --exit-node="${SELECTED_NODE}" --exit-node-allow-lan-access=true
      log_ok "Túnel Completo activado: Todo tu tráfico de internet ahora navega por ${SELECTED_NODE}."
      ;;
    mesh|malla|direct|none)
      log_info "Cambiando a MODO MALLA (Mesh)..."
      sudo tailscale set --exit-node=""
      log_ok "Modo Malla activado: Solo el tráfico interno de VPN viaja por el túnel; tu internet general sale directo."
      ;;
    *)
      log_err "Modo desconocido '${TARGET_MODE}'. Opciones: 'mesh' o 'full [IP_EXIT_NODE]'"
      exit 1
      ;;
  esac
}

cmd_toggle() {
  require_tailscale
  local CURRENT_EXIT
  CURRENT_EXIT=$(tailscale status 2>/dev/null | grep "active; exit node" | awk '{print $1}' || true)

  if [[ -n "${CURRENT_EXIT}" ]]; then
    cmd_mode mesh
  else
    cmd_mode full "${EXIT_NODE}"
  fi
}

cmd_autostart() {
  local ACTION="${1:-status}"
  case "${ACTION}" in
    enable|on|1)
      log_info "Habilitando inicio automático de Tailscale en el arranque..."
      sudo systemctl enable tailscaled
      log_ok "Inicio automático habilitado."
      ;;
    disable|off|0)
      log_info "Deshabilitando inicio automático de Tailscale en el arranque..."
      sudo systemctl disable tailscaled
      log_ok "Inicio automático deshabilitado."
      ;;
    status)
      if sudo systemctl is-enabled tailscaled >/dev/null 2>&1; then
        echo -e "Inicio automático: ${CLR_GREEN}HABILITADO${CLR_RESET}"
      else
        echo -e "Inicio automático: ${CLR_YELLOW}DESHABILITADO${CLR_RESET}"
      fi
      ;;
    *)
      log_err "Uso: $0 autostart [enable|disable|status]"
      exit 1
      ;;
  esac
}

cmd_proxy() {
  local ACTION="${1:-status}"
  case "${ACTION}" in
    enable|on|1)
      log_info "Activando Proxy nativo de Tailscale (SOCKS5 :1080 | HTTP :8080)..."
      sudo bash -c '
cat << "EOF" > /etc/default/tailscaled
PORT="41641"
FLAGS="--socks5-server=localhost:1080 --outbound-http-proxy-listen=localhost:8080"
EOF
systemctl restart tailscaled
'
      log_ok "Proxy SOCKS5 activo en 127.0.0.1:1080 y HTTP Proxy en 127.0.0.1:8080."
      ;;
    disable|off|0)
      log_info "Desactivando Proxy nativo de Tailscale..."
      sudo bash -c '
cat << "EOF" > /etc/default/tailscaled
PORT="41641"
FLAGS=""
EOF
systemctl restart tailscaled
'
      log_ok "Proxy desactivado."
      ;;
    status)
      if ss -tulpn 2>/dev/null | grep -q "127.0.0.1:1080"; then
        echo -e "Proxy nativo: ${CLR_GREEN}ACTIVO (SOCKS5: 127.0.0.1:1080, HTTP: 127.0.0.1:8080)${CLR_RESET}"
      else
        echo -e "Proxy nativo: ${CLR_YELLOW}INACTIVO${CLR_RESET}"
      fi
      ;;
    *)
      log_err "Uso: $0 proxy [enable|disable|status]"
      exit 1
      ;;
  esac
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
  echo "Comandos de Conexión:"
  echo "  up | connect                  Conectar Tailscale al servidor Headscale"
  echo "  down | disconnect             Desconectar VPN"
  echo "  status                        Ver estado de la VPN, IPs, Exit Node, Proxy y Peers"
  echo ""
  echo "Modos de Enrutamiento:"
  echo "  mode mesh                     Modo Malla (solo red privada VPN, internet directo)"
  echo "  mode full [IP_EXIT_NODE]      Túnel Completo (todo internet cifrado por el Exit Node)"
  echo "  switch | toggle               Alternar entre Modo Malla y Túnel Completo"
  echo ""
  echo "Proxy y Sistema:"
  echo "  proxy [enable|disable|status] Activar o desactivar el Proxy SOCKS5/HTTP nativo"
  echo "  autostart [enable|disable]    Habilitar o deshabilitar inicio con el sistema"
  echo "  ping                          Probar latencia contra el servidor VPS"
  echo "  help                          Mostrar esta ayuda"
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
    cmd_mode "$@"
    ;;
  switch|toggle)
    cmd_toggle
    ;;
  autostart)
    cmd_autostart "$@"
    ;;
  proxy)
    cmd_proxy "$@"
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
