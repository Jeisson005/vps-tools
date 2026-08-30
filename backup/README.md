# 📦 Sistema de Backup Automatizado del VPS a Google Drive

Sistema integral de copias de seguridad en la nube para el VPS con cifrado simétrico militar **GPG (AES-256)**, subida a **Google Drive** vía **Rclone**, auto-detección de bases de datos Docker y política de retención **GFS (Grandfather-Father-Son)**.

---

## 🎯 Características Principales

1. **Respaldos Completos por Defecto:**
   * Empaqueta todo el directorio de usuario (`$HOME`: proyectos, configuraciones, `.bashrc`, claves SSH, `.env`).
   * **Filtros inteligentes:** Omite automáticamente cachés (`.cache/`, `.npm/`), `node_modules/`, entornos virtuales (`venv/`, `.venv/`) y logs masivos para que el archivo sea ligero y rápido de subir.
2. **Auto-descubrimiento de Bases de Datos:**
   * Detecta automáticamente contenedores activos de **PostgreSQL**, **MySQL/MariaDB**, **MongoDB** y **Redis**.
   * Realiza volcados consistentes (`pg_dumpall`, `mysqldump`, `mongodump`, `redis bgsave`) antes de empaquetar.
3. **Cifrado de Seguridad Extremo (GPG AES-256):**
   * Ninguna contraseña, token o base de datos viaja en texto claro a Google Drive.
   * El archivo se cifra en el servidor con tu clave maestra antes de ser transmitido.
4. **Política de Retención GFS (19 Copias Máximo):**
   * **7 Diarias:** Mantiene exactamente los últimos 7 días en `vps-tools-backups/daily/`.
   * **12 Mensuales:** Mantiene 1 copia por cada uno de los últimos 12 meses en `vps-tools-backups/monthly/`.
   * Las copias viejas que superen los límites se eliminan automáticamente de Drive en cada ejecución.

---

## 🚀 Puesta en Marcha Rápida

### 1. Vincular Google Drive con Rclone (Una sola vez)

Ejecuta el asistente interactivo:
```bash
./scripts/setup_rclone.sh
```
El asistente instalará `rclone` y abrirá la configuración para conectar tu cuenta de Google Drive bajo el nombre `gdrive`.

### 2. Configurar Variables de Entorno

Copia la plantilla y define tu contraseña maestra de cifrado:
```bash
cp .env.example .env
chmod 600 .env
nano .env
```
Asegúrate de definir:
* `BACKUP_ENCRYPTION_KEY`: Una contraseña segura para cifrar/descifrar tus backups.
* `RCLONE_REMOTE=gdrive:vps-tools-backups`

---

## 💻 Uso de los Scripts

### Ejecutar Backup Diario (GFS, rota según retención)
```bash
./scripts/backup.sh
# O explícitamente:
./scripts/backup.sh daily
```

### Ejecutar Backup Manual (Permanente, no expira)
```bash
./scripts/backup.sh manual
```

### Listar Backups en Google Drive (Daily, Monthly y Manual)
```bash
./scripts/restore.sh list
```

### Probar Integridad de un Backup (Descarga y verifica sin extraer)
```bash
./scripts/restore.sh test backup_daily_20260830_030000.tar.gz.gpg
```

### Restaurar Archivos
```bash
./scripts/restore.sh restore backup_daily_20260830_030000.tar.gz.gpg /tmp/recuperacion
```

---

## ⏰ Programación Automática (Cron)

Para que el backup se ejecute todos los días a las **3:30 AM** (hora del servidor):

Edita tu crontab con `crontab -e` y añade:

```cron
# Backup diario del VPS a Google Drive con retención de 7 días y 12 meses
30 3 * * * /path/to/vps-tools/backup/scripts/backup.sh >> /path/to/vps-tools/cron/logs/backup.log 2>&1
```

O revisa la plantilla en [`cron/crontab.example`](file:///home/jeisson/Documents/Artic%20proyectos/vps-tools/cron/crontab.example).
