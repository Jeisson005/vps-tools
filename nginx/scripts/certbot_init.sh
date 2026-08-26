#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  CERTBOT_EMAIL="${CERTBOT_EMAIL:-$(grep -E '^CERTBOT_EMAIL=' .env 2>/dev/null | cut -d= -f2- | tr -d '\"'\'' ')}"
fi

: "${CERTBOT_EMAIL:?Missing CERTBOT_EMAIL in .env or environment}"

DOMAIN="${1:-}"
if [[ -z "${DOMAIN}" ]]; then
  echo "Usage: bash scripts/certbot_init.sh <domain>" >&2
  exit 1
fi

mkdir -p certbot/www certbot/conf certbot/logs

# Ensure Nginx is up on HTTP to respond to the challenge
docker compose up -d core

# Obtain certificate using HTTP-01 (webroot)
docker compose --profile certbot run --rm \
  certbot certonly \
  --webroot -w /var/www/certbot \
  -d "$DOMAIN" \
  --email "$CERTBOT_EMAIL" \
  --agree-tos \
  --non-interactive \
  --keep-until-expiring \
  --config-dir /etc/letsencrypt \
  --work-dir /etc/letsencrypt \
  --logs-dir /var/log/letsencrypt

echo "Certificate ready at: certbot/conf/live/${DOMAIN}/"