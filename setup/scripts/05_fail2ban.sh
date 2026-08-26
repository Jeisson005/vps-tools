#!/usr/bin/env bash
set -euo pipefail

echo "==> [05/11] Configuring Fail2ban brute-force protection..."

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

SSH_PORT="${SSH_PORT:-22}"
FAIL2BAN_BANTIME="${FAIL2BAN_BANTIME:-1h}"
FAIL2BAN_FINDTIME="${FAIL2BAN_FINDTIME:-10m}"
FAIL2BAN_MAXRETRY="${FAIL2BAN_MAXRETRY:-5}"

JAIL_LOCAL="/etc/fail2ban/jail.local"

cat <<EOF > "$JAIL_LOCAL"
[DEFAULT]
# Modern systemd journal backend for Ubuntu 24.04+/Debian 12+ compatibility
backend = systemd
bantime = $FAIL2BAN_BANTIME
findtime = $FAIL2BAN_FINDTIME
maxretry = $FAIL2BAN_MAXRETRY
banaction = ufw
banaction_allports = ufw

[sshd]
enabled = true
port = $SSH_PORT
maxretry = $FAIL2BAN_MAXRETRY
EOF

echo "--> Enabling and restarting fail2ban..."
systemctl enable fail2ban
systemctl restart fail2ban

sleep 1
if command -v fail2ban-client &>/dev/null; then
  echo "--> Fail2ban SSH jail status:"
  fail2ban-client status sshd 2>/dev/null || echo "Fail2ban is active."
fi
