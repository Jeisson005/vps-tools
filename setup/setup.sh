#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Colors
RED="\e[31m"
GREEN="\e[32m"
YELLOW="\e[33m"
BLUE="\e[34m"
CYAN="\e[36m"
BOLD="\e[1m"
RESET="\e[0m"

# Ensure root privileges
if [[ $EUID -ne 0 ]]; then
  echo -e "${RED}${BOLD}Error: This script must be run as root or with sudo.${RESET}" >&2
  exit 1
fi

# Load .env if present
if [[ -f .env ]]; then
  echo -e "${CYAN}--> Loading configuration from setup/.env...${RESET}"
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
elif [[ -f .env.example ]]; then
  echo -e "${YELLOW}--> No .env found. Using defaults from .env.example (or environment)...${RESET}"
  set -a
  # shellcheck disable=SC1091
  source .env.example
  set +a
fi

SCRIPTS_DIR="./scripts"

run_all() {
  echo -e "${BOLD}${GREEN}==============================================================================${RESET}"
  echo -e "${BOLD}${GREEN}  STARTING FULL VPS INITIAL SETUP & HARDENING                                 ${RESET}"
  echo -e "${BOLD}${GREEN}==============================================================================${RESET}"
  
  bash "$SCRIPTS_DIR/01_system_packages.sh"
  bash "$SCRIPTS_DIR/02_create_user.sh"
  bash "$SCRIPTS_DIR/03_ssh_hardening.sh"
  bash "$SCRIPTS_DIR/04_ufw_firewall.sh"
  bash "$SCRIPTS_DIR/05_fail2ban.sh"
  bash "$SCRIPTS_DIR/06_timezone_swap.sh"
  bash "$SCRIPTS_DIR/07_security_upgrades.sh"
  bash "$SCRIPTS_DIR/08_journald_tuning.sh"
  bash "$SCRIPTS_DIR/09_clean_motd.sh"
  bash "$SCRIPTS_DIR/10_sysctl_bbr.sh"
  bash "$SCRIPTS_DIR/11_docker_install.sh"

  echo ""
  echo -e "${BOLD}${GREEN}==============================================================================${RESET}"
  echo -e "${BOLD}${GREEN}  VPS INITIAL SETUP COMPLETED SUCCESSFULLY!                                   ${RESET}"
  echo -e "${BOLD}${GREEN}==============================================================================${RESET}"
  echo -e "${CYAN}Next recommended steps:${RESET}"
  echo -e " 1. Test SSH login in a new terminal session before closing this one:"
  echo -e "    ${YELLOW}ssh ${NEW_USER:-deploy}@<SERVER_IP> -p ${SSH_PORT:-22}${RESET}"
  echo -e " 2. Navigate to any service in vps-tools (e.g. nginx, postgres, redis, mongodb) and deploy."
  echo ""
}

# Non-interactive CLI flag support
if [[ "${1:-}" == "--all" ]] || [[ "${1:-}" == "-y" ]] || [[ "${1:-}" == "all" ]]; then
  run_all
  exit 0
fi

# Interactive Menu
show_menu() {
  clear 2>/dev/null || true
  echo -e "${BOLD}${CYAN}==============================================================================${RESET}"
  echo -e "${BOLD}${CYAN}  VPS-TOOLS : INITIAL SERVER PROVISIONING & HARDENING                        ${RESET}"
  echo -e "${BOLD}${CYAN}==============================================================================${RESET}"
  echo -e "  ${BOLD}1)${RESET}  Run ALL setup steps in sequence (Recommended for fresh VPS)"
  echo -e "  ${BOLD}2)${RESET}  [01] System update & essential tools"
  echo -e "  ${BOLD}3)${RESET}  [02] Create non-root user & sudo configuration"
  echo -e "  ${BOLD}4)${RESET}  [03] SSH security hardening & port configuration"
  echo -e "  ${BOLD}5)${RESET}  [04] UFW Firewall (SSH, HTTP, HTTPS, custom)"
  echo -e "  ${BOLD}6)${RESET}  [05] Fail2ban brute-force protection"
  echo -e "  ${BOLD}7)${RESET}  [06] Timezone & Swapfile (with swappiness tuning)"
  echo -e "  ${BOLD}8)${RESET}  [07] Unattended security upgrades"
  echo -e "  ${BOLD}9)${RESET}  [08] Journald log retention tuning"
  echo -e "  ${BOLD}10)${RESET} [09] Clean MOTD (Disable ads & install custom status dashboard)"
  echo -e "  ${BOLD}11)${RESET} [10] TCP BBR & Kernel network optimizations"
  echo -e "  ${BOLD}12)${RESET} [11] Install Docker Engine & Docker Compose plugin"
  echo -e "  ${BOLD}0)${RESET}  Exit"
  echo -e "${BOLD}${CYAN}==============================================================================${RESET}"
  read -rp "Select an option [0-12]: " opt
  echo ""

  case "$opt" in
    1) run_all ;;
    2) bash "$SCRIPTS_DIR/01_system_packages.sh" ;;
    3) bash "$SCRIPTS_DIR/02_create_user.sh" ;;
    4) bash "$SCRIPTS_DIR/03_ssh_hardening.sh" ;;
    5) bash "$SCRIPTS_DIR/04_ufw_firewall.sh" ;;
    6) bash "$SCRIPTS_DIR/05_fail2ban.sh" ;;
    7) bash "$SCRIPTS_DIR/06_timezone_swap.sh" ;;
    8) bash "$SCRIPTS_DIR/07_security_upgrades.sh" ;;
    9) bash "$SCRIPTS_DIR/08_journald_tuning.sh" ;;
    10) bash "$SCRIPTS_DIR/09_clean_motd.sh" ;;
    11) bash "$SCRIPTS_DIR/10_sysctl_bbr.sh" ;;
    12) bash "$SCRIPTS_DIR/11_docker_install.sh" ;;
    0) echo "Exiting."; exit 0 ;;
    *) echo -e "${RED}Invalid option.${RESET}" ;;
  esac
}

show_menu
