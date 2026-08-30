#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${BASE_DIR}/.env"

# Load environment configuration if available
if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
fi

send_telegram() {
  local msg="$1"
  if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d "chat_id=${TELEGRAM_CHAT_ID}" \
      -d "text=${msg}" \
      -d "parse_mode=Markdown" >/dev/null 2>&1 || true
  fi
}

on_error() {
  local exit_code="$?"
  local line="$1"
  local cmd="$2"
  echo "[-] ERROR: Certbot renewal failed at line ${line} (exit code ${exit_code}, command: '${cmd}')" >&2
  send_telegram "🚨 *ALERTA: Falló la Renovación SSL (Certbot)* 🚨%0A%0A🖥️ *Host:* \`$(hostname)\`%0A⚠️ *Línea:* \`${line}\`%0A🔧 *Comando:* \`${cmd}\`%0A❌ *Código:* \`${exit_code}\`%0A📁 *Revisa logs en:* \`${BASE_DIR}/logs/\`"
}
trap 'on_error ${LINENO} "${BASH_COMMAND}"' ERR

cd "${BASE_DIR}"

mkdir -p certbot/www certbot/conf certbot/logs

echo "[+] Running Certbot renewal check..."

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
  echo "[+] Reloading Nginx configuration..."
  docker compose exec -T core nginx -s reload
fi

echo "[+] ✓ Certbot renewal check completed successfully."

if [[ "${NOTIFY_ON_SUCCESS:-false}" == "true" ]]; then
  send_telegram "✅ *Renovación SSL Nginx Exitosa* ✅%0A%0A🖥️ *Host:* \`$(hostname)\`%0A🔒 Certificados SSL verificados y actualizados."
fi
