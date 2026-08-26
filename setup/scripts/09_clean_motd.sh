#!/usr/bin/env bash
set -euo pipefail

echo "==> [09/11] Cleaning MOTD ads and setting up custom Artic server banner..."

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

CUSTOM_MOTD_BANNER="${CUSTOM_MOTD_BANNER:-yes}"
MOTD_AUTHOR="${MOTD_AUTHOR:-Jeisson}"
MOTD_WELCOME_MSG="${MOTD_WELCOME_MSG:-Welcome to Artic Jeisson server!}"
MOTD_SHOW_METRICS="${MOTD_SHOW_METRICS:-yes}"

# 1. Clear static Contabo ASCII art and text
if [[ -f /etc/motd ]]; then
  echo "--> Clearing /etc/motd..."
  truncate -s 0 /etc/motd
fi

# 2. Disable ads, Canonical ESM banners and spam in update-motd.d
if [[ -d /etc/update-motd.d ]]; then
  echo "--> Disabling ESM and promotional MOTD scripts..."
  chmod -x /etc/update-motd.d/10-help-text 2>/dev/null || true
  chmod -x /etc/update-motd.d/50-motd-news 2>/dev/null || true
  chmod -x /etc/update-motd.d/88-esm-announce 2>/dev/null || true
  chmod -x /etc/update-motd.d/91-contract-ua-esm-status 2>/dev/null || true
fi

# 3. Disable motd-news service
if [[ -f /etc/default/motd-news ]]; then
  sed -i 's/^ENABLED=.*/ENABLED=0/' /etc/default/motd-news 2>/dev/null || echo "ENABLED=0" >> /etc/default/motd-news
fi

# 4. Create dynamic dashboard banner with Artic ASCII Art
if [[ "$CUSTOM_MOTD_BANNER" == "yes" ]]; then
  mkdir -p /etc/update-motd.d
  BANNER_SCRIPT="/etc/update-motd.d/99-server-info"

  cat <<EOF > "$BANNER_SCRIPT"
#!/bin/bash
# Artic Server Status & Welcome Banner

CYAN="\e[36m"
GREEN="\e[32m"
YELLOW="\e[33m"
BLUE="\e[34m"
MAGENTA="\e[35m"
BOLD="\e[1m"
RESET="\e[0m"

echo ""
echo -e "\${BOLD}\${CYAN}    /\\      ___   _     _   ___ \${RESET}"
echo -e "\${BOLD}\${CYAN}   /  \\    |  _| | |_  ( ) |  _|\${RESET}"
echo -e "\${BOLD}\${CYAN}  /    \\   | |   |  _| | | | |  \${RESET}"
echo -e "\${BOLD}\${CYAN} /    / \\  | |   | |_  | | | |_ \${RESET}"
echo -e "\${BOLD}\${CYAN}/____/___\\ |_|   |___| |_| |___|\${RESET}"
echo -e "\${BOLD}\${BLUE}                      By $MOTD_AUTHOR\${RESET}"
echo ""
echo -e "\${BOLD}\${GREEN}$MOTD_WELCOME_MSG\${RESET}"
echo ""

if [[ "$MOTD_SHOW_METRICS" == "yes" ]]; then
  hostname="\$(hostname)"
  os_name="\$(grep -oP '(?<=PRETTY_NAME=).+' /etc/os-release 2>/dev/null | tr -d '\"' || uname -sr)"
  kernel="\$(uname -r)"
  uptime_str="\$(uptime -p 2>/dev/null | sed 's/up //' || uptime)"

  # System Metrics
  load_avg="\$(cut -d' ' -f1-3 /proc/loadavg)"
  cpu_cores="\$(nproc 2>/dev/null || echo 1)"
  
  read -r _ total used _ < <(free -m | grep -i mem)
  mem_pct=\$(( used * 100 / total ))
  mem_info="\${used}/\${total} MB (\${mem_pct}%)"

  read -r _ d_total d_used _ d_pct _ < <(df -h / | tail -n 1)
  disk_info="\${d_used}/\${d_total} (\${d_pct})"

  main_ip="\$(ip route get 1.1.1.1 2>/dev/null | awk '{print \$7; exit}' || hostname -I | awk '{print \$1}')"

  echo -e "\${BOLD}\${BLUE}==============================================================================\${RESET}"
  echo -e "\${BOLD}\${GREEN}  SYSTEM STATUS : \${hostname} (\${os_name})\${RESET}"
  echo -e "\${BOLD}\${BLUE}==============================================================================\${RESET}"
  printf "  \${BOLD}%-16s\${RESET} : %s (Kernel: %s)\n" "OS & Kernel" "\$os_name" "\$kernel"
  printf "  \${BOLD}%-16s\${RESET} : %s\n" "Uptime" "\$uptime_str"
  printf "  \${BOLD}%-16s\${RESET} : %s (%s Cores)\n" "CPU Load" "\$load_avg" "\$cpu_cores"
  printf "  \${BOLD}%-16s\${RESET} : %s\n" "Memory Usage" "\$mem_info"
  printf "  \${BOLD}%-16s\${RESET} : %s\n" "Disk Usage (/)" "\$disk_info"
  printf "  \${BOLD}%-16s\${RESET} : %s\n" "Server IP" "\$main_ip"
  echo -e "\${BOLD}\${BLUE}==============================================================================\${RESET}"
  echo ""
fi
EOF

  chmod +x "$BANNER_SCRIPT"
  echo "--> Artic dynamic MOTD banner created at $BANNER_SCRIPT"
fi
