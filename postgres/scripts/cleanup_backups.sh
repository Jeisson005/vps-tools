#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

umask 077

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

if [[ ! "$RETENTION_DAYS" =~ ^[0-9]+$ ]] || [[ "$RETENTION_DAYS" -le 0 ]]; then
  echo "RETENTION_DAYS must be a positive integer" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

# Best-effort cleanup of old dumps
find "$BACKUP_DIR" -type f -name "*.dump" -mtime "+$RETENTION_DAYS" -delete || true
