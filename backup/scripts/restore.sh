#!/usr/bin/env bash
# ==============================================================================
# VPS Backup Restoration & Inspection Helper
# Lists, downloads, decrypts, and extracts backups from Google Drive.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${BASE_DIR}/.env"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
fi

RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive:vps-tools-backups}"
BACKUP_ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"
TEMP_RESTORE_DIR="${TEMP_DIR:-/tmp/vps-backups}/restore_staging"

ensure_key() {
  if [[ -z "${BACKUP_ENCRYPTION_KEY}" ]]; then
    read -r -s -p "Introduce tu clave maestra para descifrar el backup: " BACKUP_ENCRYPTION_KEY
    echo ""
  fi
  if [[ -z "${BACKUP_ENCRYPTION_KEY}" ]]; then
    echo "[-] ERROR: Se requiere la clave de cifrado para continuar." >&2
    exit 1
  fi
}

usage() {
  echo "Usage: $0 {list|test <file>|download <file>|restore <file> <target_dir>}"
  echo ""
  echo "Commands:"
  echo "  list                      List all daily and monthly backups available in Google Drive"
  echo "  test <file_name>          Download and test archive integrity (decrypt + tar verify)"
  echo "  download <file_name>      Download a backup file from Google Drive to local staging"
  echo "  restore <file> <target>   Download, decrypt and extract files to <target_dir>"
  echo ""
  echo "Examples:"
  echo "  $0 list"
  echo "  $0 test backup_daily_20260830_030000.tar.gz.gpg"
  echo "  $0 restore backup_daily_20260830_030000.tar.gz.gpg /tmp/recovered_data"
  exit 1
}

CMD="${1:-}"

case "${CMD}" in
  list)
    echo "================================================================="
    echo "☁️  Backups in Google Drive: ${RCLONE_REMOTE}"
    echo "================================================================="
    echo ""
    echo "📅 Daily Backups (Latest 7):"
    rclone lsl "${RCLONE_REMOTE}/daily/" --tpslimit 2 2>/dev/null || echo "  (none found)"
    echo ""
    echo "📆 Monthly Backups (Latest 12):"
    rclone lsl "${RCLONE_REMOTE}/monthly/" --tpslimit 2 2>/dev/null || echo "  (none found)"
    echo ""
    echo "📌 Manual Backups (Permanent):"
    rclone lsl "${RCLONE_REMOTE}/manual/" --tpslimit 2 2>/dev/null || echo "  (none found)"
    echo ""
    ;;

  download)
    FILE="${2:-}"
    [[ -z "${FILE}" ]] && usage

    mkdir -p "${TEMP_RESTORE_DIR}"
    echo "[+] Searching for ${FILE} in ${RCLONE_REMOTE}..."

    # Check if file is in daily, monthly or manual
    if rclone lsf "${RCLONE_REMOTE}/daily/${FILE}" --tpslimit 2 &>/dev/null; then
      SOURCE_PATH="${RCLONE_REMOTE}/daily/${FILE}"
    elif rclone lsf "${RCLONE_REMOTE}/monthly/${FILE}" --tpslimit 2 &>/dev/null; then
      SOURCE_PATH="${RCLONE_REMOTE}/monthly/${FILE}"
    elif rclone lsf "${RCLONE_REMOTE}/manual/${FILE}" --tpslimit 2 &>/dev/null; then
      SOURCE_PATH="${RCLONE_REMOTE}/manual/${FILE}"
    else
      echo "[-] File ${FILE} not found in daily/, monthly/, or manual/ on remote." >&2
      exit 1
    fi

    echo "[+] Downloading ${SOURCE_PATH} -> ${TEMP_RESTORE_DIR}/${FILE}..."
    rclone copy "${SOURCE_PATH}" "${TEMP_RESTORE_DIR}/" --tpslimit 2 --drive-chunk-size 64M --progress
    echo "[+] Downloaded to: ${TEMP_RESTORE_DIR}/${FILE}"
    ;;

  test)
    FILE="${2:-}"
    [[ -z "${FILE}" ]] && usage

    mkdir -p "${TEMP_RESTORE_DIR}"
    LOCAL_GPG="${TEMP_RESTORE_DIR}/${FILE}"

    if [[ ! -f "${LOCAL_GPG}" ]]; then
      "${SCRIPT_DIR}/restore.sh" download "${FILE}"
    fi

    LOCAL_TAR="${LOCAL_GPG%.gpg}"
    ensure_key
    echo "[+] Decrypting test copy with GPG..."
    gpg --batch --yes --decrypt \
        --passphrase "${BACKUP_ENCRYPTION_KEY}" \
        --output "${LOCAL_TAR}" \
        "${LOCAL_GPG}"

    echo "[+] Verifying tarball integrity and listing contents..."
    tar -ztvf "${LOCAL_TAR}" | head -n 30
    echo "[...] (Truncated output)"
    echo "[+] Checking full tar archive for errors..."
    tar -ztf "${LOCAL_TAR}" > /dev/null

    rm -f "${LOCAL_TAR}"
    echo ""
    echo "================================================================="
    echo "✅ Backup integrity verified: OK (Archive is valid and decryptable)"
    echo "================================================================="
    ;;

  restore)
    FILE="${2:-}"
    TARGET="${3:-}"
    if [[ -z "${FILE}" || -z "${TARGET}" ]]; then
      usage
    fi

    mkdir -p "${TARGET}" "${TEMP_RESTORE_DIR}"
    LOCAL_GPG="${TEMP_RESTORE_DIR}/${FILE}"

    if [[ ! -f "${LOCAL_GPG}" ]]; then
      "${SCRIPT_DIR}/restore.sh" download "${FILE}"
    fi

    LOCAL_TAR="${LOCAL_GPG%.gpg}"
    ensure_key
    echo "[+] Decrypting archive..."
    gpg --batch --yes --decrypt \
        --passphrase "${BACKUP_ENCRYPTION_KEY}" \
        --output "${LOCAL_TAR}" \
        "${LOCAL_GPG}"

    echo "[+] Extracting files to: ${TARGET}..."
    tar -zxpf "${LOCAL_TAR}" -C "${TARGET}"

    rm -f "${LOCAL_TAR}"
    echo ""
    echo "================================================================="
    echo "🎉 Restoration completed successfully into ${TARGET}"
    echo "================================================================="
    ;;

  *)
    usage
    ;;
esac
