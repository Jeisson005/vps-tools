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
BACKUP_EXCLUDE_DBS="${BACKUP_EXCLUDE_DBS:-}"

mkdir -p "$BACKUP_DIR"

now_utc="$(date -u +"%Y%m%dT%H%M%SZ")"

# List all non-template DBs (including 'postgres' unless excluded)
dbs="$(
  docker compose exec -T db \
    psql -U "$POSTGRES_USER" -d postgres -Atc \
    "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;"
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

  out="$BACKUP_DIR/${db}_${now_utc}.dump"
  echo "Backing up '$db' -> $out" >&2

  docker compose exec -T db \
    pg_dump \
      -U "$POSTGRES_USER" \
      -d "$db" \
      --format=custom \
      --no-owner \
      --no-privileges \
    < /dev/null > "$out"

done <<< "$dbs"

# Retention (best-effort)
if [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]] && [[ "$RETENTION_DAYS" -gt 0 ]]; then
  find "$BACKUP_DIR" -type f -name "*.dump" -mtime "+$RETENTION_DAYS" -delete || true
fi
