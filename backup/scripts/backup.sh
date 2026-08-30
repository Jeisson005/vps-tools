#!/usr/bin/env bash
# ==============================================================================
# VPS Automated Backup & GFS Retention Script
# Backs up $SOURCE_DIR, active Docker databases, and configs.
# Encrypts via GPG (AES-256) and uploads to Google Drive with Rclone.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${BASE_DIR}/.env"
EXCLUDE_FILE="${BASE_DIR}/config/exclude.list"

# 1. Load Environment Configuration
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[-] ERROR: Configuration file not found at ${ENV_FILE}" >&2
  echo "    Please copy ${BASE_DIR}/.env.example to ${ENV_FILE} and configure it." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"

RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive:vps-tools-backups}"
BACKUP_ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
RETENTION_MONTHS="${RETENTION_MONTHS:-12}"
SOURCE_DIR="${SOURCE_DIR:-/home/jeisson}"
TEMP_DIR="${TEMP_DIR:-/tmp/vps-backups}"

if [[ -z "${BACKUP_ENCRYPTION_KEY}" ]]; then
  echo "[-] ERROR: BACKUP_ENCRYPTION_KEY is not defined in ${ENV_FILE}" >&2
  exit 1
fi

# 2. Verify Required CLI Tools
for tool in tar gzip gpg rclone; do
  if ! command -v "${tool}" &>/dev/null; then
    echo "[-] ERROR: Required tool '${tool}' is not installed or not in PATH." >&2
    exit 1
  fi
done

TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
DATE_DAY="$(date +"%d")"
DATE_MONTH="$(date +"%Y%m")"

RUN_ID="backup_daily_${TIMESTAMP}"
STAGING_DIR="${TEMP_DIR}/${RUN_ID}"
DB_DUMP_DIR="${STAGING_DIR}/db_dumps"
TAR_FILE="${TEMP_DIR}/${RUN_ID}.tar.gz"
GPG_FILE="${TAR_FILE}.gpg"

echo "================================================================="
echo "🚀 Starting VPS Backup: ${RUN_ID}"
echo "📅 Date: $(date -R)"
echo "📂 Source Directory: ${SOURCE_DIR}"
echo "☁️  Remote Target: ${RCLONE_REMOTE}"
echo "================================================================="

# Create Clean Staging Directories
rm -rf "${STAGING_DIR}" "${TAR_FILE}" "${GPG_FILE}" 2>/dev/null || true
mkdir -p "${STAGING_DIR}" "${DB_DUMP_DIR}"

cleanup() {
  echo "[*] Cleaning up local staging files in ${TEMP_DIR}..."
  rm -rf "${STAGING_DIR}" "${TAR_FILE}" "${GPG_FILE}" 2>/dev/null || true
}
trap cleanup EXIT

# 3. Auto-discover & Dump Active Databases from Docker
if command -v docker &>/dev/null && docker ps -q &>/dev/null; then
  echo "[+] Inspecting active Docker containers for databases..."

  # PostgreSQL Auto-Discovery
  PG_CONTAINERS=$(docker ps --format '{{.Names}}' | grep -iE 'postgres|psql|db' || true)
  for c in ${PG_CONTAINERS}; do
    # Check if container actually has pg_dumpall or psql
    if docker exec "${c}" which pg_dumpall &>/dev/null; then
      echo "  [pg] Dumping PostgreSQL from container '${c}'..."
      # Attempt pg_dumpall with user postgres or default
      if docker exec "${c}" pg_dumpall -U postgres 2>/dev/null | gzip > "${DB_DUMP_DIR}/pg_${c}_dump.sql.gz"; then
        echo "  [pg] ✓ PostgreSQL dump complete for '${c}' ($(du -sh "${DB_DUMP_DIR}/pg_${c}_dump.sql.gz" | cut -f1))"
      else
        echo "  [pg] ⚠️ pg_dumpall failed with default user 'postgres' on '${c}', skipping."
        rm -f "${DB_DUMP_DIR}/pg_${c}_dump.sql.gz" 2>/dev/null || true
      fi
    fi
  done

  # MySQL / MariaDB Auto-Discovery
  MYSQL_CONTAINERS=$(docker ps --format '{{.Names}}' | grep -iE 'mysql|mariadb' || true)
  for c in ${MYSQL_CONTAINERS}; do
    if docker exec "${c}" which mysqldump &>/dev/null; then
      echo "  [mysql] Dumping MySQL from container '${c}'..."
      if docker exec "${c}" mysqldump --all-databases -u root 2>/dev/null | gzip > "${DB_DUMP_DIR}/mysql_${c}_dump.sql.gz"; then
        echo "  [mysql] ✓ MySQL dump complete for '${c}' ($(du -sh "${DB_DUMP_DIR}/mysql_${c}_dump.sql.gz" | cut -f1))"
      else
        rm -f "${DB_DUMP_DIR}/mysql_${c}_dump.sql.gz" 2>/dev/null || true
      fi
    fi
  done

  # MongoDB Auto-Discovery
  MONGO_CONTAINERS=$(docker ps --format '{{.Names}}' | grep -iE 'mongo' || true)
  for c in ${MONGO_CONTAINERS}; do
    if docker exec "${c}" which mongodump &>/dev/null; then
      echo "  [mongo] Dumping MongoDB from container '${c}'..."
      if docker exec "${c}" mongodump --archive 2>/dev/null | gzip > "${DB_DUMP_DIR}/mongo_${c}_dump.archive.gz"; then
        echo "  [mongo] ✓ MongoDB dump complete for '${c}'"
      else
        rm -f "${DB_DUMP_DIR}/mongo_${c}_dump.archive.gz" 2>/dev/null || true
      fi
    fi
  done

  # Redis Auto-Discovery
  REDIS_CONTAINERS=$(docker ps --format '{{.Names}}' | grep -iE 'redis' || true)
  for c in ${REDIS_CONTAINERS}; do
    if docker exec "${c}" which redis-cli &>/dev/null; then
      echo "  [redis] Requesting BGSAVE from container '${c}'..."
      docker exec "${c}" redis-cli bgsave &>/dev/null || true
      sleep 2
      if docker cp "${c}:/data/dump.rdb" "${DB_DUMP_DIR}/redis_${c}_dump.rdb" 2>/dev/null; then
        echo "  [redis] ✓ Redis dump saved for '${c}'"
      fi
    fi
  done
fi

# 4. Empaquetado del Sistema con Filtros de Exclusión
echo "[+] Creating archive from ${SOURCE_DIR}..."
TAR_ARGS=(
  -czf "${TAR_FILE}"
)

if [[ -f "${EXCLUDE_FILE}" ]]; then
  echo "  [tar] Applying exclude rules from ${EXCLUDE_FILE}"
  TAR_ARGS+=(--exclude-from="${EXCLUDE_FILE}")
fi

# Also exclude the staging and temp dirs explicitly
TAR_ARGS+=(
  --exclude="${TEMP_DIR}"
  --exclude="${STAGING_DIR}"
)

# Append extra staging DB dumps if created
set +e
if [[ -d "${DB_DUMP_DIR}" && "$(ls -A "${DB_DUMP_DIR}" 2>/dev/null)" ]]; then
  echo "  [tar] Including container database dumps..."
  tar "${TAR_ARGS[@]}" -C "${SOURCE_DIR}" . -C "${STAGING_DIR}" db_dumps
  TAR_EXIT=$?
else
  tar "${TAR_ARGS[@]}" -C "${SOURCE_DIR}" .
  TAR_EXIT=$?
fi
set -e

# GNU tar returns 0 on success, 1 on file changed/unreadable warnings, 2 on fatal
if [[ ${TAR_EXIT} -gt 1 ]]; then
  echo "[-] ERROR: tar failed with fatal exit code ${TAR_EXIT}" >&2
  exit "${TAR_EXIT}"
fi

UNENC_SIZE="$(du -sh "${TAR_FILE}" | cut -f1)"
echo "[+] Archive compressed successfully (${UNENC_SIZE})"

# 5. Encrypt Archive with GPG AES-256
echo "[+] Encrypting archive with GPG AES-256..."
gpg --batch --yes --symmetric \
    --cipher-algo AES256 \
    --passphrase "${BACKUP_ENCRYPTION_KEY}" \
    --output "${GPG_FILE}" \
    "${TAR_FILE}"

ENC_SIZE="$(du -sh "${GPG_FILE}" | cut -f1)"
echo "[+] Encryption complete (${ENC_SIZE})"

# Remove raw unencrypted tarball immediately
rm -f "${TAR_FILE}"

# 6. Upload to Google Drive (Daily)
REMOTE_NAME="${RCLONE_REMOTE%%:*}"
if ! rclone lsd "${REMOTE_NAME}:" &>/dev/null; then
  echo "[-] WARNING: Rclone remote '${REMOTE_NAME}' is not configured yet or not accessible." >&2
  echo "    Please run '${SCRIPT_DIR}/setup_rclone.sh' to link your Google Drive account." >&2
  echo "    The encrypted backup has been preserved locally at: ${TEMP_DIR}/${RUN_ID}.tar.gz.gpg" >&2
  trap - EXIT
  rm -rf "${STAGING_DIR}" "${TAR_FILE}" 2>/dev/null || true
  exit 0
fi

echo "[+] Uploading to Google Drive: ${RCLONE_REMOTE}/daily/..."
rclone copy "${GPG_FILE}" "${RCLONE_REMOTE}/daily/" \
  --fast-list \
  --progress

echo "[+] ✓ Daily backup uploaded: ${RUN_ID}.tar.gz.gpg"

# 7. Monthly Copy Promotion
# If 1st of month OR if no backup exists yet for this month
MONTHLY_DEST="${RCLONE_REMOTE}/monthly/backup_monthly_${DATE_MONTH}.tar.gz.gpg"
MONTHLY_EXISTS=$(rclone lsf "${RCLONE_REMOTE}/monthly/" 2>/dev/null | grep "backup_monthly_${DATE_MONTH}" || true)

if [[ "${DATE_DAY}" == "01" || -z "${MONTHLY_EXISTS}" ]]; then
  echo "[+] Promoting backup to Monthly: ${MONTHLY_DEST}..."
  rclone copyto "${GPG_FILE}" "${MONTHLY_DEST}"
  echo "[+] ✓ Monthly backup recorded for ${DATE_MONTH}"
fi

# 8. Grandfather-Father-Son Retention Enforcement
echo "[+] Enforcing Retention Policy..."

# A) Daily Backups Retention (Max $RETENTION_DAYS)
echo "  [retention] Checking daily backups (max ${RETENTION_DAYS})..."
DAILY_FILES=$(rclone lsf "${RCLONE_REMOTE}/daily/" --files-only 2>/dev/null | sort || true)
DAILY_COUNT=$(echo "${DAILY_FILES}" | grep -c . || true)

if [[ ${DAILY_COUNT} -gt ${RETENTION_DAYS} ]]; then
  EXCESS=$((DAILY_COUNT - RETENTION_DAYS))
  echo "  [retention] Found ${DAILY_COUNT} daily backups. Deleting oldest ${EXCESS}..."
  echo "${DAILY_FILES}" | head -n "${EXCESS}" | while IFS= read -r file; do
    if [[ -n "${file}" ]]; then
      echo "  [delete] Removing ${RCLONE_REMOTE}/daily/${file}..."
      rclone delete "${RCLONE_REMOTE}/daily/${file}"
    fi
  done
else
  echo "  [retention] Daily backups within limit (${DAILY_COUNT}/${RETENTION_DAYS})."
fi

# B) Monthly Backups Retention (Max $RETENTION_MONTHS)
echo "  [retention] Checking monthly backups (max ${RETENTION_MONTHS})..."
MONTHLY_FILES=$(rclone lsf "${RCLONE_REMOTE}/monthly/" --files-only 2>/dev/null | sort || true)
MONTHLY_COUNT=$(echo "${MONTHLY_FILES}" | grep -c . || true)

if [[ ${MONTHLY_COUNT} -gt ${RETENTION_MONTHS} ]]; then
  EXCESS=$((MONTHLY_COUNT - RETENTION_MONTHS))
  echo "  [retention] Found ${MONTHLY_COUNT} monthly backups. Deleting oldest ${EXCESS}..."
  echo "${MONTHLY_FILES}" | head -n "${EXCESS}" | while IFS= read -r file; do
    if [[ -n "${file}" ]]; then
      echo "  [delete] Removing ${RCLONE_REMOTE}/monthly/${file}..."
      rclone delete "${RCLONE_REMOTE}/monthly/${file}"
    fi
  done
else
  echo "  [retention] Monthly backups within limit (${MONTHLY_COUNT}/${RETENTION_MONTHS})."
fi

echo "================================================================="
echo "🎉 VPS Backup and Retention Finished Successfully!"
echo "📦 Backup Name: ${RUN_ID}.tar.gz.gpg"
echo "🔐 Encrypted: GPG AES-256"
echo "☁️  Remote: ${RCLONE_REMOTE}"
echo "================================================================="
