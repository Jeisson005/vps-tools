#!/usr/bin/env bash
set -euo pipefail

echo "========================================================================"
echo "  HERMES AGENT STATUS"
echo "========================================================================"
if command -v hermes &>/dev/null; then
  echo "--> Hermes CLI Path: $(which hermes)"
  hermes --version || true
else
  echo "[-] hermes command not found in PATH"
fi
echo "========================================================================"
