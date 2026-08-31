#!/usr/bin/env bash
# ==============================================================================
# RustDesk Server & Web Client Status
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

docker compose ps
echo ""
if [[ -f "data/id_ed25519.pub" ]]; then
  echo "🔑 Server Public Key: $(cat data/id_ed25519.pub)"
fi
