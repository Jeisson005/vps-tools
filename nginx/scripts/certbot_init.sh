#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${CERTBOT_EMAIL:?Missing CERTBOT_EMAIL in .env}"

DOMAIN="${1:-}"
if [[ -z "${DOMAIN}" ]]; then
  echo "Usage: bash scripts/certbot_init.sh <domain>" >&2
  exit 1
fi

mkdir -p certbot/www certbot/conf certbot/logs

# Ensure Nginx is up on HTTP to respond to the challenge
# Note: the challenge is served from the HTTP/HTTPS vhosts that include
# /.well-known/acme-challenge/ apuntando a /var/www/certbot.
docker compose up -d core

# Obtain certificate using HTTP-01 (webroot)
docker compose --profile certbot run --rm \
  certbot certonly \
  --webroot -w /var/www/certbot \
  -d "$DOMAIN" \
  --email "$CERTBOT_EMAIL" \
  --agree-tos \
  --non-interactive \
  --keep-until-expiring

echo "Certificate ready at: certbot/conf/live/${DOMAIN}/"