#!/usr/bin/env bash
set -euo pipefail

echo "==> [03/11] Applying SSH security hardening..."

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

SSH_PORT="${SSH_PORT:-22}"
DISABLE_ROOT_SSH="${DISABLE_ROOT_SSH:-yes}"
DISABLE_PASSWORD_AUTH="${DISABLE_PASSWORD_AUTH:-yes}"
NEW_USER="${NEW_USER:-deploy}"

USER_HOME="$(eval echo "~$NEW_USER")"
AUTH_KEYS_FILE="$USER_HOME/.ssh/authorized_keys"

# Safety check: Prevent accidental lockout if password auth is disabled without keys
if [[ "$DISABLE_PASSWORD_AUTH" == "yes" ]]; then
  has_user_key=$([[ -s "$AUTH_KEYS_FILE" ]] && echo 1 || echo 0)
  has_root_key=$([[ -s /root/.ssh/authorized_keys ]] && echo 1 || echo 0)
  
  if [[ "$has_user_key" -eq 0 ]] && [[ "$has_root_key" -eq 0 ]]; then
    echo "WARNING: No SSH public keys found in '$AUTH_KEYS_FILE' or '/root/.ssh/authorized_keys'!"
    echo "To avoid locking yourself out, PasswordAuthentication will NOT be disabled yet."
    echo "Add your public key to '$AUTH_KEYS_FILE' and re-run this script."
    DISABLE_PASSWORD_AUTH="no"
  fi
fi

# Ensure sshd_config.d directory exists
mkdir -p /etc/ssh/sshd_config.d

HARDENING_CONF="/etc/ssh/sshd_config.d/99-hardening.conf"

cat <<EOF > "$HARDENING_CONF"
# Managed by vps-tools setup
Port $SSH_PORT
PubkeyAuthentication yes
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
X11Forwarding no
EOF

if [[ "$DISABLE_ROOT_SSH" == "yes" ]]; then
  echo "PermitRootLogin no" >> "$HARDENING_CONF"
else
  echo "PermitRootLogin prohibit-password" >> "$HARDENING_CONF"
fi

if [[ "$DISABLE_PASSWORD_AUTH" == "yes" ]]; then
  cat <<EOF >> "$HARDENING_CONF"
PasswordAuthentication no
ChallengeResponseAuthentication no
KbdInteractiveAuthentication no
EOF
else
  echo "PasswordAuthentication yes" >> "$HARDENING_CONF"
fi

# Verify SSH configuration syntax
echo "--> Testing sshd configuration syntax..."
if sshd -t; then
  echo "--> Syntax OK. Reloading SSH service..."
  systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || service ssh restart
  echo "--> SSH hardening applied successfully."
else
  echo "ERROR: Invalid sshd configuration. Reverting changes..." >&2
  rm -f "$HARDENING_CONF"
  exit 1
fi
