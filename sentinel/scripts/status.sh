#!/usr/bin/env bash
set -euo pipefail

echo "========================================================================"
echo "  SENTINEL SERVICE STATUS"
echo "========================================================================"
systemctl status sentinel.service --no-pager || true
echo "------------------------------------------------------------------------"
echo "  HEALTHCHECK API (http://127.0.0.1:8006/health)"
curl -s http://127.0.0.1:8006/health || echo "[-] Service not reachable on port 8006"
echo ""
echo "========================================================================"
