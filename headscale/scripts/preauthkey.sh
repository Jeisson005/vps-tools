#!/usr/bin/env bash
# ==============================================================================
# Helper to Generate Headscale Pre-Auth Keys for Zero-Touch Device Enrollment
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

USER="${1:-jeisson}"
EXPIRATION="${2:-100y}"
REUSABLE="${3:-reusable}"
TAG="${4:-}"

# Map 'inf', 'never', '100y' to 876000h (100 years)
if [[ "${EXPIRATION}" == "inf" || "${EXPIRATION}" == "never" || "${EXPIRATION}" == "100y" ]]; then
  EXPIRATION="876000h"
fi

REUSABLE_FLAG=""
if [[ "${REUSABLE}" == "reusable" ]]; then
  REUSABLE_FLAG="--reusable"
fi

TAG_FLAG=""
if [[ -n "${TAG}" ]]; then
  TAG_FLAG="--tags ${TAG}"
fi

echo "[+] Generating pre-auth key for user '${USER}' (valid for ${EXPIRATION}, ${REUSABLE})..."
# shellcheck disable=SC2086
docker compose exec headscale headscale preauthkeys create \
  --user "${USER}" \
  --expiration "${EXPIRATION}" \
  ${REUSABLE_FLAG} \
  ${TAG_FLAG}
