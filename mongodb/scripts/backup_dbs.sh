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
BACKUP_EXCLUDE_DBS="${BACKUP_EXCLUDE_DBS:-admin,config,local}"

mkdir -p "$BACKUP_DIR"

now_utc="$(date -u +"%Y%m%dT%H%M%SZ")"

# List all databases
dbs="$(
  docker compose exec -T db \
    mongosh -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --quiet \
    --eval "db.adminCommand('listDatabases').databases.map(d => d.name).join('\n')"
)"

exclude_match() {
  local name="$1"
  [[ -z "$BACKUP_EXCLUDE_DBS" ]] && return 1
  IFS=',' read -r -a excluded <<< "$BACKUP_EXCLUDE_DBS"
  for ex in "${excluded[@]}"; do
    ex="${ex//[[:space:]]/}"
    [[ -z "$ex" ]] && continue
    [[ "$name" == "$ex" ]] && return 0
  done
  return 1
}

while IFS= read -r db; do
  [[ -z "$db" ]] && continue
  if exclude_match "$db"; then
    continue
  fi

  out="$BACKUP_DIR/${db}_${now_utc}.archive.gz"
  echo "Backing up MongoDB database '$db' -> $out" >&2

  docker compose exec -T db \
    mongodump \
      -u "$MONGO_INITDB_ROOT_USERNAME" \
      -p "$MONGO_INITDB_ROOT_PASSWORD" \
      --authenticationDatabase admin \
      --db "$db" \
      --archive \
      --gzip \
    < /dev/null > "$out"

done <<< "$dbs"

echo "MongoDB backups completed successfully." >&2

# Retention (best-effort)
if [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]] && [[ "$RETENTION_DAYS" -gt 0 ]]; then
  find "$BACKUP_DIR" -type f \( -name "*.archive.gz" -o -name "*.gz" \) -mtime "+$RETENTION_DAYS" -delete || true
fi
