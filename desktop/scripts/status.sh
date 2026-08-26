#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a; source .env; set +a
elif [[ -f .env.example ]]; then
  set -a; source .env.example; set +a
fi

DESKTOP_USER="${DESKTOP_USER:-jeisson}"

echo "========================================================================"
echo "  REMOTE DESKTOP STATUS (KASMVNC & XRDP)"
echo "========================================================================"
echo "--> KasmVNC Socket (On-Demand):"
systemctl status kasmvnc.socket --no-pager || true

echo ""
echo "--> KasmVNC Desktop Session (kasmvnc@${DESKTOP_USER}):"
systemctl status "kasmvnc@${DESKTOP_USER}" --no-pager || true

echo ""
echo "--> XRDP Service:"
systemctl status xrdp --no-pager || true

echo ""
echo "--> Listening Ports:"
ss -tulpn | grep -E "8444|8445|3389|vnc|xrdp" || true
echo "========================================================================"
