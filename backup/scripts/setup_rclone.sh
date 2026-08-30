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
  echo "📁 Carpetas 'vps-tools-backups/daily' y 'vps-tools-backups/monthly' listas en Drive."
else
  echo "⚠️ Aún no se ha detectado el remote 'gdrive'. Puedes ejecutar 'rclone config' en cualquier momento."
fi
