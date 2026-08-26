#!/usr/bin/env bash
set -euo pipefail

echo "==> [07/11] Configuring unattended security updates..."

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

cat <<EOF > /etc/apt/apt.conf.d/20auto-upgrades
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

systemctl enable unattended-upgrades || true
systemctl restart unattended-upgrades || true

echo "--> Automatic security updates configured successfully."
