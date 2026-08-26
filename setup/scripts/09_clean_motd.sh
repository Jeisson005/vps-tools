#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> [09/11] Cleaning MOTD ads and configuring custom banner from template..."

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

# Load .env if present
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
elif [[ -f .env.example ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.example
  set +a
fi

CUSTOM_MOTD_BANNER="${CUSTOM_MOTD_BANNER:-yes}"
MOTD_AUTHOR="${MOTD_AUTHOR:-Admin}"
MOTD_WELCOME_MSG="${MOTD_WELCOME_MSG:-Welcome to your server!}"
MOTD_SHOW_METRICS="${MOTD_SHOW_METRICS:-yes}"
MOTD_BANNER_FILE="${MOTD_BANNER_FILE:-}"

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

# 4. Resolve banner source (Local override -> banner.txt -> templates/motd_banner.txt)
RESOLVED_BANNER_SRC=""
if [[ -n "$MOTD_BANNER_FILE" ]] && [[ -f "$MOTD_BANNER_FILE" ]]; then
  RESOLVED_BANNER_SRC="$MOTD_BANNER_FILE"
elif [[ -f "banner.txt" ]]; then
  RESOLVED_BANNER_SRC="banner.txt"
elif [[ -f "custom_banner.txt" ]]; then
  RESOLVED_BANNER_SRC="custom_banner.txt"
elif [[ -f "templates/motd_banner.txt" ]]; then
  RESOLVED_BANNER_SRC="templates/motd_banner.txt"
fi

INSTALLED_BANNER="/etc/motd_banner.txt"

if [[ -n "$RESOLVED_BANNER_SRC" ]]; then
  echo "--> Rendering banner template from '$RESOLVED_BANNER_SRC' -> $INSTALLED_BANNER..."
  sed -e "s/{{MOTD_AUTHOR}}/$MOTD_AUTHOR/g" \
      -e "s/{{MOTD_WELCOME_MSG}}/$MOTD_WELCOME_MSG/g" \
      "$RESOLVED_BANNER_SRC" > "$INSTALLED_BANNER"
else
  echo "--> Creating fallback default $INSTALLED_BANNER..."
  cat <<EOF > "$INSTALLED_BANNER"
========================================================================
                      By $MOTD_AUTHOR

$MOTD_WELCOME_MSG
========================================================================
EOF
fi

# 5. Create dynamic dashboard script /etc/update-motd.d/99-server-info
if [[ "$CUSTOM_MOTD_BANNER" == "yes" ]]; then
  mkdir -p /etc/update-motd.d
  BANNER_SCRIPT="/etc/update-motd.d/99-server-info"

  cat <<'EOF' > "$BANNER_SCRIPT"
#!/bin/bash
# Dynamic Artic MOTD Banner & Metrics Dashboard

CYAN="\e[36m"
GREEN="\e[32m"
BLUE="\e[34m"
BOLD="\e[1m"
RESET="\e[0m"

BANNER_FILE="/etc/motd_banner.txt"

echo ""
# Read and colorize the external banner file
if [[ -f "$BANNER_FILE" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" =~ By[[:space:]]+ ]]; then
      echo -e "${BOLD}${BLUE}${line}${RESET}"
    elif [[ "$line" =~ Welcome|server!|Welcome[[:space:]]to ]]; then
      echo -e "${BOLD}${GREEN}${line}${RESET}"
    else
      echo -e "${BOLD}${CYAN}${line}${RESET}"
    fi
  done < "$BANNER_FILE"
fi
echo ""

# System Metrics Dashboard
hostname="$(hostname)"
os_name="$(grep -oP '(?<=PRETTY_NAME=).+' /etc/os-release 2>/dev/null | tr -d '\"' || uname -sr)"
kernel="$(uname -r)"
uptime_str="$(uptime -p 2>/dev/null | sed 's/up //' || uptime)"

load_avg="$(cut -d' ' -f1-3 /proc/loadavg)"
cpu_cores="$(nproc 2>/dev/null || echo 1)"

read -r _ total used _ < <(free -m | grep -i mem)
mem_pct=$(( used * 100 / total ))
mem_info="${used}/${total} MB (${mem_pct}%)"

read -r _ d_total d_used _ d_pct _ < <(df -h / | tail -n 1)
disk_info="${d_used}/${d_total} (${d_pct})"

main_ip="$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}' || hostname -I | awk '{print $1}')"

  echo -e "${BOLD}${GREEN}  SYSTEM STATUS : ${hostname} (${os_name})${RESET}"
  echo ""
  printf "  ${BOLD}%-16s${RESET} : %s (Kernel: %s)\n" "OS & Kernel" "$os_name" "$kernel"
  printf "  ${BOLD}%-16s${RESET} : %s\n" "Uptime" "$uptime_str"
  printf "  ${BOLD}%-16s${RESET} : %s (%s Cores)\n" "CPU Load" "$load_avg" "$cpu_cores"
  printf "  ${BOLD}%-16s${RESET} : %s\n" "Memory Usage" "$mem_info"
  printf "  ${BOLD}%-16s${RESET} : %s\n" "Disk Usage (/)" "$disk_info"
  printf "  ${BOLD}%-16s${RESET} : %s\n" "Server IP" "$main_ip"
  echo ""
EOF

  chmod +x "$BANNER_SCRIPT"
  echo "--> Dynamic MOTD configured to read from $INSTALLED_BANNER"
fi
