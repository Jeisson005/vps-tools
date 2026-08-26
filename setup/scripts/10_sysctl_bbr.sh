#!/usr/bin/env bash
set -euo pipefail

echo "==> [10/11] Optimizing TCP BBR & Kernel network parameters..."

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

ENABLE_BBR="${ENABLE_BBR:-yes}"

SYSCTL_CONF="/etc/sysctl.d/99-network-tuning.conf"

cat <<EOF > "$SYSCTL_CONF"
# Network & Kernel optimization by vps-tools setup
fs.file-max = 2097152
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 8192
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 8192
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15
EOF

if [[ "$ENABLE_BBR" == "yes" ]]; then
  cat <<EOF >> "$SYSCTL_CONF"
# Google BBR Congestion Control
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
EOF
fi

echo "--> Applying sysctl parameters..."
sysctl -p "$SYSCTL_CONF" >/dev/null 2>&1 || true

# Verify BBR
if [[ "$ENABLE_BBR" == "yes" ]]; then
  current_cc="$(sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null || echo 'unknown')"
  echo "--> Current TCP Congestion Control: $current_cc"
fi
