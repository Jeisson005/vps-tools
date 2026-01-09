#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

DOMAIN="${1:-localhost}"

CERT_DIR="certbot/conf/live/${DOMAIN}"

HTTPS_CONF="conf.d/${DOMAIN}.https.conf"
HTTPS_DISABLED_CONF="conf.d/${DOMAIN}.https.conf.disabled"
HTTP_CONF="conf.d/${DOMAIN}.http.conf"
HTTP_DISABLED_CONF="conf.d/${DOMAIN}.http.conf.disabled"

docker compose up -d core

if [[ ! -f "${CERT_DIR}/fullchain.pem" || ! -f "${CERT_DIR}/privkey.pem" ]]; then
  echo "Couldn't find certificates in ${CERT_DIR}." >&2
  echo "Run first: bash scripts/certbot_init.sh ${DOMAIN}" >&2
  exit 1
fi

if [[ -f "$HTTP_CONF" ]]; then
  mv "$HTTP_CONF" "$HTTP_DISABLED_CONF"
fi

if [[ -f "$HTTPS_DISABLED_CONF" ]]; then
  mv "$HTTPS_DISABLED_CONF" "$HTTPS_CONF"
fi

if [[ ! -f "$HTTPS_CONF" ]]; then
  echo "${HTTPS_CONF} does not exist (.disabled or .conf)." >&2
  exit 1
fi

docker compose exec core nginx -t

docker compose exec core nginx -s reload
