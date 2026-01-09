#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose up -d core

DOMAIN="${1:-localhost}"

HTTPS_CONF="conf.d/${DOMAIN}.https.conf"
HTTPS_DISABLED_CONF="conf.d/${DOMAIN}.https.conf.disabled"
HTTP_CONF="conf.d/${DOMAIN}.http.conf"
HTTP_DISABLED_CONF="conf.d/${DOMAIN}.http.conf.disabled"

if [[ -f "$HTTPS_CONF" ]]; then
  mv "$HTTPS_CONF" "$HTTPS_DISABLED_CONF"
fi

if [[ -f "$HTTP_DISABLED_CONF" ]]; then
  mv "$HTTP_DISABLED_CONF" "$HTTP_CONF"
fi

# Ensure HTTP mode exists
if [[ ! -f "$HTTP_CONF" ]]; then
  echo "${HTTP_CONF} does not exist" >&2
  exit 1
fi

docker compose exec core nginx -t

docker compose exec core nginx -s reload
