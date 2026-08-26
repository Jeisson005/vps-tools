#!/usr/bin/env bash
set -euo pipefail

echo "==> [04/11] Configuring UFW firewall rules..."

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

SSH_PORT="${SSH_PORT:-22}"
UFW_EXTRA_PORTS="${UFW_EXTRA_PORTS:-80 443}"
ENABLE_UFW="${ENABLE_UFW:-yes}"

if [[ "$ENABLE_UFW" != "yes" ]]; then
  echo "--> UFW setup skipped by configuration."
  exit 0
fi

echo "--> Setting default firewall policies..."
ufw default deny incoming
ufw default allow outgoing

echo "--> Allowing SSH on port $SSH_PORT..."
ufw allow "$SSH_PORT/tcp" comment 'SSH'

for port in $UFW_EXTRA_PORTS; do
  echo "--> Allowing port $port/tcp..."
  ufw allow "$port/tcp" comment "Custom port $port"
done

echo "--> Enabling UFW..."
ufw --force enable

echo "--> Firewall status:"
ufw status verbose
