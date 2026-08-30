#!/usr/bin/env bash
# ==============================================================================
# Helper to install Rclone and configure Google Drive remote
# ==============================================================================

set -euo pipefail

echo "================================================================="
echo "🔧 Configuración de Rclone para Google Drive en tu VPS"
echo "================================================================="

# 1. Instalar rclone si no existe
if ! command -v rclone &>/dev/null; then
  echo "[+] Instalando rclone oficial..."
  curl -fsSL https://rclone.org/install.sh | sudo bash
  echo "[+] ✓ Rclone instalado correctamente ($(rclone --version | head -n1))"
else
  echo "[+] ✓ Rclone ya está instalado ($(rclone --version | head -n1))"
fi

echo ""
echo "================================================================="
echo "📋 Pasos para vincular tu Google Drive:"
echo "================================================================="
echo "1. Ejecuta: rclone config"
echo "2. Elige: 'n' (New remote)"
echo "3. Nombre: 'gdrive'"
echo "4. Storage: 'drive' (Google Drive)"
echo "5. client_id y client_secret: Presiona ENTER (dejar en blanco)"
echo "6. scope: Elige '1' (Full access all files)"
echo "7. service_account_file: ENTER (en blanco)"
echo "8. Edit advanced config: 'n' (No)"
echo "9. Use web browser to authenticate: 'n' (No, porque es un VPS sin monitor)"
echo "   -> Te dará un comando que puedes correr en tu PC local, o un enlace web"
echo "   -> Pegas el código de autorización aquí y listo."
echo "10. Configure as a team drive: 'n' (No)"
echo "11. Confirmar y salir con 'q'."
echo "================================================================="
echo ""
read -r -p "¿Deseas iniciar 'rclone config' ahora mismo? [s/N]: " RESP
if [[ "${RESP}" =~ ^[sSyY]$ ]]; then
  rclone config
fi

echo ""
echo "[+] Verificando conexión con Google Drive..."
if rclone lsd gdrive: &>/dev/null; then
  echo "✅ ¡Conexión exitosa con Google Drive!"
  rclone mkdir gdrive:vps-tools-backups/daily 2>/dev/null || true
  rclone mkdir gdrive:vps-tools-backups/monthly 2>/dev/null || true
  rclone mkdir gdrive:vps-tools-backups/manual 2>/dev/null || true
  echo "📁 Carpetas 'daily', 'monthly' y 'manual' listas en Drive."
else
  echo "⚠️ Aún no se ha detectado el remote 'gdrive'. Puedes ejecutar 'rclone config' en cualquier momento."
fi

# 2. Configurar Clave Maestra de Cifrado
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${BASE_DIR}/.env"

echo ""
echo "================================================================="
echo "🔐 Configuración de la Clave Maestra de Cifrado (GPG AES-256)"
echo "================================================================="
echo "⚠️  IMPORTANTE: Los backups se cifran para que nadie pueda leer tus"
echo "   archivos o contraseñas en Google Drive. Debes guardar esta clave"
echo "   en tu gestor de contraseñas personal (1Password, Bitwarden, etc.)."
echo "   Sin esta clave, NO podrás recuperar tus datos si el VPS se destruye."
echo "================================================================="

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${BASE_DIR}/.env.example" "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
fi

CURRENT_KEY=$(grep -E '^BACKUP_ENCRYPTION_KEY=' "${ENV_FILE}" | cut -d'=' -f2- | tr -d '"' || true)

if [[ -n "${CURRENT_KEY}" && "${CURRENT_KEY}" != *"ChangeThis"* ]]; then
  echo "Tu clave actual configurada es:"
  echo "👉 ${CURRENT_KEY}"
  echo ""
  read -r -p "¿Deseas cambiarla por una propia ahora? [s/N]: " CHANGE_KEY
  if [[ "${CHANGE_KEY}" =~ ^[sSyY]$ ]]; then
    read -r -s -p "Introduce tu nueva clave maestra: " NEW_KEY
    echo ""
    if [[ -n "${NEW_KEY}" ]]; then
      sed -i "s/^BACKUP_ENCRYPTION_KEY=.*/BACKUP_ENCRYPTION_KEY=\"${NEW_KEY}\"/" "${ENV_FILE}"
      echo "✅ Clave maestra actualizada en ${ENV_FILE}."
    fi
  fi
else
  read -r -s -p "Introduce tu clave maestra de cifrado: " USER_KEY
  echo ""
  if [[ -z "${USER_KEY}" ]]; then
    USER_KEY=$(openssl rand -hex 24)
    echo "Se ha generado una clave segura aleatoria: ${USER_KEY}"
  fi
  sed -i "s/^BACKUP_ENCRYPTION_KEY=.*/BACKUP_ENCRYPTION_KEY=\"${USER_KEY}\"/" "${ENV_FILE}"
  echo "✅ Clave maestra guardada en ${ENV_FILE}."
  echo "⚠️  Cópiala y guárdala ahora en tu gestor de contraseñas: ${USER_KEY}"
fi
