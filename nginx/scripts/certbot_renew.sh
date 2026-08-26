#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p certbot/www certbot/conf certbot/logs

# Renew if needed (certbot decides if it's close to expiring)
docker compose run --rm --user root \
  certbot renew \
  --webroot -w /var/www/certbot \
  --config-dir /etc/letsencrypt \
  --work-dir /etc/letsencrypt \
  --logs-dir /var/log/letsencrypt

# Fix permissions on renewed certificates
docker compose run --rm --user root \
  --entrypoint chmod certbot -R a+rX /etc/letsencrypt/live /etc/letsencrypt/archive

# Reload Nginx so it picks up the renewed certificate
if docker compose ps --status=running --services | grep -q '^core$'; then
  docker compose exec -T core nginx -s reload
fi
