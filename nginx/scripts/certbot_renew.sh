#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p certbot/www certbot/conf certbot/logs

# Renew if needed (certbot decides if it's close to expiring)
docker compose --profile certbot run --rm \
  certbot renew \
  --webroot -w /var/www/certbot \
  --quiet \
  --config-dir /etc/letsencrypt \
  --work-dir /etc/letsencrypt \
  --logs-dir /var/log/letsencrypt

# Reload Nginx so it picks up the renewed certificate
if docker compose ps --status=running --services | grep -q '^core$'; then
  docker compose exec core nginx -s reload
fi
