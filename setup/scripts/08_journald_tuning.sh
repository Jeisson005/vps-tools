#!/usr/bin/env bash
set -euo pipefail

echo "==> [08/11] Tuning systemd journald log limits..."

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

JOURNAL_MAX_USE="${JOURNAL_MAX_USE:-500M}"

mkdir -p /etc/systemd/journald.conf.d

cat <<EOF > /etc/systemd/journald.conf.d/size.conf
[Journal]
SystemMaxUse=$JOURNAL_MAX_USE
SystemMaxFileSize=100M
MaxRetentionSec=30day
EOF

systemctl restart systemd-journald

echo "--> Journald log limit set to $JOURNAL_MAX_USE (retention 30 days)."
