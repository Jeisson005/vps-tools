#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

umask 077

if [[ ! -f .env ]]; then
  echo "Missing .env (copy .env.example -> .env and configure it)" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

now_utc="$(date -u +"%Y%m%dT%H%M%SZ")"
out="$BACKUP_DIR/redis_${now_utc}.rdb.gz"

echo "Triggering Redis BGSAVE..." >&2
docker compose exec -T redis redis-cli -a "$REDIS_PASSWORD" bgsave >/dev/null 2>&1 || true

# Wait briefly for background save to finish
sleep 2

echo "Exporting Redis dump to $out" >&2
docker compose exec -T redis sh -c "cat /data/dump.rdb 2>/dev/null || true" | gzip -9 > "$out"

# Verify dump file is not empty
if [[ ! -s "$out" ]]; then
  echo "Warning: dump file is empty. Trying direct sync dump..." >&2
  docker compose exec -T redis redis-cli -a "$REDIS_PASSWORD" --rdb - | gzip -9 > "$out"
fi

echo "Redis backup saved successfully -> $out" >&2

# Retention cleanup (best-effort)
if [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]] && [[ "$RETENTION_DAYS" -gt 0 ]]; then
  find "$BACKUP_DIR" -type f \( -name "*.rdb.gz" -o -name "*.rdb" \) -mtime "+$RETENTION_DAYS" -delete || true
fi
